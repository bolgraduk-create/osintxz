"""Backend-backed view model for the authoritative QML desktop shell.

The bridge deliberately contains presentation mapping only. Database access and
business operations stay in the existing controllers and application services.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import logging
from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.interface.desktop.workers import OsintCollectionWorker
from app.osint.models import OsintTargetType


LOGGER = logging.getLogger(__name__)


class DesktopBridge(QObject):
    """Expose existing OSINTXZ application services to QML."""

    changed = Signal()
    navigationRequested = Signal(str)
    messageChanged = Signal()
    PAGE_SIZE = 100

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._cases: list[dict[str, Any]] = []
        self._workspaces: dict[str, dict[str, Any]] = {}
        self._current_case_id = ""
        self._search_results: list[dict[str, Any]] = []
        self._osint_run: dict[str, Any] = {}
        self._osint_busy = False
        self._osint_thread: QThread | None = None
        self._osint_worker: OsintCollectionWorker | None = None
        self._osint_context: dict[str, Any] = {}
        self._page_records: dict[str, list[dict[str, Any]]] = {}
        self._page_offsets: dict[str, int] = {}
        self._page_totals: dict[str, int] = {}
        self._page_loading: set[str] = set()
        self._page_errors: dict[str, str] = {}
        self._last_page = ""
        self._connector_cache = None
        self._message = ""
        self._database_available = True
        self._generation = 0
        self.refresh()

    @Property(int, notify=changed)
    def generation(self) -> int:
        return self._generation

    @Property(str, constant=True)
    def accountDisplayName(self) -> str:
        # The existing application has no authentication/session user model.
        return "Local workspace"

    @Property(str, constant=True)
    def accountRole(self) -> str:
        return "No authenticated user"

    @Property(str, constant=True)
    def accountInitials(self) -> str:
        return "LW"

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property(bool, notify=changed)
    def databaseAvailable(self) -> bool:
        return self._database_available

    @Property(str, notify=changed)
    def currentCaseId(self) -> str:
        return self._current_case_id

    @Property(str, notify=changed)
    def currentCaseTitle(self) -> str:
        case = self._case_by_id(self._current_case_id)
        return str(case.get("title") or "") if case else ""

    @Property(bool, notify=changed)
    def hasCurrentCase(self) -> bool:
        return bool(self._current_case_id)

    @Property("QVariantMap", notify=changed)
    def osintRun(self) -> dict[str, Any]:
        return dict(self._osint_run)

    @Property(bool, notify=changed)
    def osintBusy(self) -> bool:
        return self._osint_busy

    @Property(int, notify=changed)
    def osintConnectorCount(self) -> int:
        return len(self._connector_records())

    @Property("QVariantMap", notify=changed)
    def dashboard(self) -> dict[str, Any]:
        entities = self._all_workspace_items("entities")
        evidence = self._all_workspace_items("evidence")
        recent_cases = [self._case_record(case) for case in self._cases[:4]]
        intelligence = self._recent_intelligence(entities, evidence)
        workspace = self._current_workspace()
        graph = workspace.get("graph", {}) if workspace else {}
        return {
            "dateLabel": datetime.now().strftime("%A, %b %d, %Y").upper(),
            "greeting": self._greeting(),
            "summary": self._dashboard_summary(len(self._cases), len(intelligence)),
            "activeCases": len(self._cases),
            "entities": self._page_totals.get("entities", len(entities)),
            "findings": self._page_totals.get("evidence", len(evidence)),
            "risks": 0,
            "recentCases": recent_cases,
            "recentIntelligence": intelligence[:4],
            "graphNodes": list(graph.get("nodes") or [])[:9],
            "graphEdges": list(graph.get("edges") or []),
            "graphCaseTitle": self.currentCaseTitle,
        }

    @Slot()
    def refresh(self) -> None:
        """Reload UI data exclusively through existing controllers/services."""
        started = perf_counter()
        try:
            cases = self._container.case_controller.get_cases() or []
            self._cases = [dict(case) for case in cases if isinstance(case, dict)]
            self._workspaces = {}
            # Test/adaptor containers may only expose the legacy workspace API.
            # Keep that compatibility path while the real container stays lazy.
            if not hasattr(self._container, "entity_service"):
                for case in self._cases:
                    case_id = str(case.get("id") or "")
                    if case_id:
                        try:
                            workspace = self._container.workspace_controller.load_workspace(case_id)
                            if isinstance(workspace, dict):
                                self._workspaces[case_id] = workspace
                        except Exception:
                            LOGGER.debug("Legacy workspace unavailable for %s", case_id, exc_info=True)
            self._page_records.clear(); self._page_offsets.clear(); self._page_totals.clear()
            self._page_errors.clear()
            for key, attr in (("entities", "entity_service"), ("evidence", "evidence_service"), ("timeline", "timeline_service"), ("reports", "report_service")):
                service = getattr(self._container, attr, None)
                if service is not None:
                    try:
                        self._page_totals[key] = int(service.count_all())
                    except Exception:
                        LOGGER.debug("Unable to count %s", key, exc_info=True)
            if self._current_case_id and self._current_case_id not in {str(c.get("id")) for c in self._cases}:
                self._current_case_id = ""
            self._database_available = True
            self._set_message("")
        except Exception as exc:
            LOGGER.exception("Unable to refresh desktop data")
            self._cases = []
            self._workspaces = {}
            self._current_case_id = ""
            self._database_available = False
            self._set_message(f"Database unavailable: {exc}")
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug("Rollback after dashboard refresh failed", exc_info=True)
        self._generation += 1
        self.changed.emit()
        LOGGER.info("Desktop refresh completed in %.1f ms (cases=%s)", (perf_counter() - started) * 1000, len(self._cases))

    @Slot(str, str, result="QVariantMap")
    def pageData(self, page: str, query: str = "") -> dict[str, Any]:
        started = perf_counter()
        page_key = (page or "").strip().lower()
        if page_key != self._last_page:
            LOGGER.info("PAGE OPEN: %s", page_key.title())
            self._last_page = page_key
        if page_key in {"entities", "evidence", "timeline", "reports"} and page_key not in self._page_records:
            self._load_page(page_key, 0, notify=False)
        records = self._records_for_page(page_key)
        normalized_query = (query or "").strip().casefold()
        if normalized_query:
            records = [
                record for record in records
                if normalized_query in " ".join(
                    str(record.get(key) or "")
                    for key in ("title", "detail", "status", "meta")
                ).casefold()
            ]
        result = {
            "metrics": self._metrics_for_page(page_key),
            "records": records,
            "contextItems": self._context_for_page(page_key),
            "emptyText": self._page_errors.get(page_key) or self._empty_text(page_key, bool(normalized_query)),
            "actionEnabled": page_key in {"cases", "osint"},
            "actionReason": "" if page_key in {"cases", "osint"} else self._disabled_reason(page_key),
            "loading": page_key in self._page_loading,
            "total": self._page_totals.get(page_key, len(records)),
            "hasMore": len(self._page_records.get(page_key, records)) < self._page_totals.get(page_key, len(records)),
        }
        elapsed = (perf_counter() - started) * 1000
        if elapsed > 50:
            LOGGER.info("Page %s model update %.1f ms (%s records)", page_key, elapsed, len(records))
        return result

    @Slot(str)
    def loadMore(self, page: str) -> None:
        key = (page or "").strip().lower()
        if key not in {"entities", "evidence", "timeline", "reports"}:
            return
        if key not in self._page_records:
            self._load_page(key, 0)
            return
        offset = self._page_offsets.get(key, 0) + self.PAGE_SIZE
        if offset < self._page_totals.get(key, 0):
            self._load_page(key, offset)

    def _load_page(self, page: str, offset: int, *, notify: bool = True) -> None:
        if page in self._page_loading:
            return
        self._page_loading.add(page)
        started = perf_counter()
        scope = self._current_case_id or "all"
        LOGGER.info("[%s] %s scope=%s offset=%s limit=%s loading=True", page.title(), "INITIAL LOAD REQUESTED" if offset == 0 else "NEXT PAGE", scope, offset, self.PAGE_SIZE)
        try:
            service = {"entities": "entity_service", "evidence": "evidence_service", "timeline": "timeline_service", "reports": "report_service"}[page]
            svc = getattr(self._container, service, None)
            if svc is None:
                items = self._selected_or_all(page)
                rows = items[offset:offset + self.PAGE_SIZE]
                total = len(items)
                mapped = [self._workspace_record(page, row) for row in rows]
            else:
                case_id = UUID(self._current_case_id) if self._current_case_id else None
                rows = svc.get_page(limit=self.PAGE_SIZE, offset=offset, case_id=case_id)
                total = svc.count_all(case_id=case_id) if offset == 0 else self._page_totals[page]
                mapped = [self._workspace_record(page, self._model_dict(row)) for row in rows]
            self._page_records.setdefault(page, []).extend(mapped)
            self._page_offsets[page] = offset
            self._page_totals[page] = int(total)
            self._page_errors.pop(page, None)
            LOGGER.info("[%s] initial=%s scope=%s offset=%s limit=%s db_rows=%s model_rows=%s total=%s has_more=%s loading=False elapsed_ms=%.1f", page.title(), offset == 0, scope, offset, self.PAGE_SIZE, len(rows), len(self._page_records[page]), total, len(self._page_records[page]) < total, (perf_counter()-started)*1000)
        except Exception:
            LOGGER.exception("Unable to load %s page", page)
            self._page_errors[page] = "Unable to load records. Reopen this page to retry."
        finally:
            self._page_loading.discard(page)
            self._generation += 1
            if notify:
                self.changed.emit()

    @staticmethod
    def _model_dict(row: Any) -> dict[str, Any]:
        if isinstance(row, dict): return row
        data = {}
        for key in ("id", "title", "description", "value", "type", "confidence", "sha256", "created_at", "updated_at", "event_time", "date"):
            try: data[key] = getattr(row, key)
            except Exception: pass
        for key in ("entity_type", "evidence_type", "event_type", "report_type"):
            value = getattr(row, key, None)
            if value is not None:
                data["type"] = getattr(value, "value", value)
                break
        data["date"] = data.get("date") or data.get("event_time") or ""
        return data

    @Slot(str, result=bool)
    def selectCase(self, case_id: str) -> bool:
        normalized = str(case_id or "").strip()
        if not self._case_by_id(normalized):
            self._set_message("The selected investigation is unavailable.")
            return False
        if normalized != self._current_case_id:
            self._page_records.clear()
            self._page_offsets.clear()
            self._page_errors.clear()
            self._osint_run = {}
        self._current_case_id = normalized
        self._set_message("")
        self._generation += 1
        self.changed.emit()
        self.navigationRequested.emit("overview")
        return True

    @Slot(str, str, result=bool)
    def createCase(self, title: str, description: str = "") -> bool:
        normalized_title = str(title or "").strip()
        if not normalized_title:
            self._set_message("Case title cannot be empty.")
            return False
        try:
            case = self._container.case_controller.create_case(
                title=normalized_title,
                description=str(description or "").strip(),
            )
        except Exception as exc:
            LOGGER.exception("Unable to create case")
            self._set_message(f"Unable to create case: {exc}")
            return False
        self.refresh()
        case_id = str(case.get("id") or "") if isinstance(case, dict) else ""
        if case_id:
            self.selectCase(case_id)
        self._set_message("Investigation created.")
        return True

    @Slot(str, str, result=bool)
    def renameCase(self, case_id: str, title: str) -> bool:
        normalized_title = str(title or "").strip()
        if not normalized_title:
            self._set_message("Case title cannot be empty.")
            return False
        try:
            renamed = self._container.case_controller.rename_case(
                str(case_id or "").strip(),
                normalized_title,
            )
        except Exception as exc:
            LOGGER.exception("Unable to rename case")
            self._set_message(f"Unable to rename case: {exc}")
            return False
        if not renamed:
            self._set_message("The selected investigation could not be renamed.")
            return False
        self.refresh()
        self._set_message("Investigation renamed.")
        return True

    @Slot(str, result=bool)
    def deleteCase(self, case_id: str) -> bool:
        normalized = str(case_id or "").strip()
        try:
            deleted = self._container.case_controller.delete_case(normalized)
        except Exception as exc:
            LOGGER.exception("Unable to delete case")
            self._set_message(f"Unable to delete case: {exc}")
            return False
        if not deleted:
            self._set_message("The selected investigation could not be deleted.")
            return False
        if normalized == self._current_case_id:
            self._current_case_id = ""
            self._osint_run = {}
        self.refresh()
        self._set_message("Investigation deleted.")
        return True

    @Slot(str, str, result=bool)
    def runOsint(self, target_type: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if not normalized_value:
            self._set_message("OSINT collection requires a target.")
            return False

        normalized_type = str(target_type or "").strip().lower()
        target_enum = {
            "email": OsintTargetType.EMAIL,
            "username": OsintTargetType.USERNAME,
            "domain": OsintTargetType.DOMAIN,
            "ip": OsintTargetType.IP,
            "url": OsintTargetType.URL,
            "phone": OsintTargetType.PHONE,
        }.get(normalized_type)
        if target_enum is None:
            self._set_message("Unsupported OSINT target type.")
            return False

        # Test/adaptor containers can still expose only the older workspace
        # controller. Production uses the investigation-aware enrichment path.
        enrichment_service = getattr(
            self._container,
            "investigation_target_enrichment_service",
            None,
        )
        if enrichment_service is None:
            return self._run_osint_workspace_fallback(
                target_type=target_enum,
                value=normalized_value,
            )

        if not self._current_case_id:
            self._set_message(
                "Select an investigation before running an OSINT collection."
            )
            return False

        if self._osint_busy:
            self._set_message("An OSINT collection is already running.")
            return False

        started_at = datetime.now()
        case_id = self._current_case_id
        case_title = self.currentCaseTitle

        self._osint_context = {
            "caseId": case_id,
            "caseTitle": case_title,
            "targetType": target_enum,
            "targetValue": normalized_value,
            "startedAt": started_at,
        }
        self._osint_run = self._running_osint_run_payload(
            target_type=target_enum,
            value=normalized_value,
            started_at=started_at,
            case_id=case_id,
            case_title=case_title,
        )
        self._osint_busy = True
        self._set_message(
            f"OSINT collection running for {normalized_value}."
        )
        self._generation += 1
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = OsintCollectionWorker(
                case_id=case_id,
                target_type=target_enum.value,
                value=normalized_value,
                timeout=30,
                use_cache=True,
            )
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_osint_worker_succeeded)
            worker.failed.connect(self._on_osint_worker_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_osint_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._osint_thread = thread
            self._osint_worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start OSINT background worker")
            self._osint_busy = False
            self._osint_thread = None
            self._osint_worker = None
            self._osint_context = {}
            self._osint_run = self._failed_osint_run_payload(
                target_type=target_enum,
                value=normalized_value,
                started_at=started_at,
                duration=0.0,
                error=str(exc),
            )
            self._set_message(f"Unable to start OSINT collection: {exc}")
            self._generation += 1
            self.changed.emit()
            return False

    @Slot(object)
    def _on_osint_worker_succeeded(self, result: object) -> None:
        context = dict(self._osint_context)
        if not context:
            return

        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            snapshot = {}
        duration = self._safe_float(payload.get("duration"))

        try:
            run_payload = self._build_enrichment_snapshot_run_payload(
                snapshot=snapshot,
                target_type=context["targetType"],
                value=str(context["targetValue"]),
                started_at=context["startedAt"],
                duration=duration,
                case_id=str(context["caseId"]),
                case_title=str(context["caseTitle"]),
            )
        except Exception as exc:
            LOGGER.exception("Unable to map OSINT background result")
            run_payload = self._failed_osint_run_payload(
                target_type=context["targetType"],
                value=str(context["targetValue"]),
                started_at=context["startedAt"],
                duration=duration,
                error=f"Unable to map collection result: {exc}",
            )

        if self._current_case_id == str(context["caseId"]):
            self._osint_run = run_payload
        else:
            # The collection belongs to the case that was selected when it
            # started. Do not show that run in a different investigation.
            self._osint_run = {}

        self._invalidate_after_osint()
        summary = run_payload.get("summary", {})
        case_suffix = (
            ""
            if self._current_case_id == str(context["caseId"])
            else f" Results were stored in {context['caseTitle']}."
        )
        self._set_message(
            "OSINT collection completed; "
            f"{int(summary.get('findings') or 0)} finding(s), "
            f"{int(summary.get('leads') or 0)} lead(s), "
            f"{int(summary.get('evidenceCreated') or 0)} evidence item(s) created."
            + case_suffix
        )
        self._generation += 1
        self.changed.emit()

    @Slot(object)
    def _on_osint_worker_failed(self, result: object) -> None:
        context = dict(self._osint_context)
        if not context:
            return


        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Unknown OSINT error")
        duration = self._safe_float(payload.get("duration"))
        failed_payload = self._failed_osint_run_payload(
            target_type=context["targetType"],
            value=str(context["targetValue"]),
            started_at=context["startedAt"],
            duration=duration,
            error=error,
        )
        failed_payload["caseId"] = str(context["caseId"])
        failed_payload["caseTitle"] = str(context["caseTitle"])

        if self._current_case_id == str(context["caseId"]):
            self._osint_run = failed_payload
        else:
            self._osint_run = {}

        self._set_message(f"OSINT collection failed: {error}")
        self._generation += 1
        self.changed.emit()

    @Slot()
    def _on_osint_thread_finished(self) -> None:
        self._osint_busy = False
        self._osint_worker = None
        self._osint_thread = None
        self._osint_context = {}
        self._generation += 1
        self.changed.emit()

    @Slot(str, result="QVariantList")
    def search(self, query: str) -> list[dict[str, Any]]:
        normalized = str(query or "").strip()
        if not normalized:
            self._search_results = []
            self._generation += 1
            self.changed.emit()
            return []
        try:
            request = InvestigationSearchQuery(
                query=normalized,
                case_id=UUID(self._current_case_id) if self._current_case_id else None,
                methods=(SearchMethod.STRUCTURED, SearchMethod.LEXICAL),
                limit=25,
                candidate_limit=50,
                enable_query_expansion=False,
                enable_reranking=False,
                enable_neural_reranking=False,
            )
            response = self._container.unified_search_service.search(request)
            self._search_results = [
                {
                    "id": str(hit.object_id),
                    "title": hit.title or str(hit.object_id),
                    "detail": hit.snippet or "No preview available",
                    "status": str(hit.object_type).replace("_", " ").title(),
                    "meta": self._score_text(hit.final_score),
                    "color": "#68a4ff",
                    "tint": "#142b47",
                }
                for hit in response.hits
            ]
            self._set_message(
                "No matching intelligence found."
                if not self._search_results
                else f"{len(self._search_results)} search result(s)."
            )
        except Exception as exc:
            LOGGER.exception("Unified search failed")
            self._search_results = []
            self._set_message(f"Search failed: {exc}")
        self._generation += 1
        self.changed.emit()
        return list(self._search_results)

    @Slot(str, str)
    def activateRecord(self, page: str, record_id: str) -> None:
        if (page or "").strip().lower() == "cases":
            self.selectCase(record_id)

    @Slot()
    def clearMessage(self) -> None:
        self._set_message("")

    def _records_for_page(self, page: str) -> list[dict[str, Any]]:
        if page == "cases":
            return [self._case_record(case) for case in self._cases]
        if page == "search":
            return list(self._search_results)
        if page == "osint":
            return self._connector_records()
        key = {
            "entities": "entities",
            "evidence": "evidence",
            "reports": "reports",
            "timeline": "timeline",
        }.get(page)
        if key:
            return list(self._page_records.get(page, []))
        if page == "graph":
            graph = self._current_workspace().get("graph", {}) if self._current_workspace() else {}
            return [
                {
                    "id": str(node.get("id") or ""),
                    "title": str(node.get("label") or "Unnamed entity"),
                    "detail": str(node.get("type") or "entity").replace("_", " ").title(),
                    "status": "Connected" if not node.get("is_isolated") else "Isolated",
                    "meta": f"{int(node.get('degree') or 0)} links",
                    "color": "#68a4ff",
                    "tint": "#142b47",
                }
                for node in list(graph.get("nodes") or [])
            ]
        return []

    def _metrics_for_page(self, page: str) -> list[dict[str, Any]]:
        records = self._records_for_page(page)
        current = self._current_workspace()
        stats = current.get("statistics", {}) if current else {}
        scope = self.currentCaseTitle or "All investigations"
        if page == "cases":
            return self._metric_set(len(self._cases), "Active cases", "Stored investigations", 0, "Selected", self.currentCaseTitle or "None", 0, "Archived", "Not exposed by current service")
        if page == "entities":
            return self._metric_set(self._page_totals.get("entities", len(records)), "Entities", scope, 0, "Entity types", "Current scope", 0, "Needs review", "No persisted review status")
        if page == "evidence":
            hashed = sum(1 for item in records if item.get("meta"))
            return self._metric_set(self._page_totals.get("evidence", len(records)), "Evidence items", scope, hashed, "Hashed", "SHA-256 recorded", 0, "Needs review", "No persisted review status")
        if page == "reports":
            return self._metric_set(self._page_totals.get("reports", len(records)), "Reports", scope, 0, "Report types", "Current scope", 0, "In review", "No workflow status model")
        if page == "timeline":
            return self._metric_set(self._page_totals.get("timeline", len(records)), "Events", scope, 0, "Event types", "Current scope", 0, "Anomalies", "No persisted anomaly metric")
        if page == "graph":
            graph_stats = (current or {}).get("graph", {}).get("statistics", {})
            return self._metric_set(int(graph_stats.get("node_count") or len(records)), "Nodes", scope, int(graph_stats.get("edge_count") or stats.get("relationships") or 0), "Relationships", "Current case", int(graph_stats.get("isolated_nodes") or 0), "Isolated", "No relationships")
        if page == "osint":
            return self._metric_set(len(records), "Connectors", "Registered by the existing pipeline", 0, "Active monitors", "No monitor model", 0, "Integrations", "No account status model")
        if page == "search":
            return self._metric_set(len(records), "Results", "Last internal search", 2, "Methods", "Structured and lexical", 0, "Queued", "Search runs immediately")
        return self._metric_set(0, "Items", "No data", 0, "Available", "No data", 0, "Pending", "No data")

    @staticmethod
    def _metric_set(a: Any, at: str, ad: str, b: Any, bt: str, bd: str, c: Any, ct: str, cd: str) -> list[dict[str, Any]]:
        return [
            {"title": at, "value": str(a), "delta": "", "subtext": ad, "color": "#68a4ff", "chart": "none"},
            {"title": bt, "value": str(b), "delta": "", "subtext": bd, "color": "#36cfa1", "chart": "none"},
            {"title": ct, "value": str(c), "delta": "", "subtext": cd, "color": "#e5a84b", "chart": "none"},
        ]

    def _context_for_page(self, page: str) -> list[dict[str, Any]]:
        if not self._database_available:
            return [{"title": "Database unavailable", "detail": self._message, "color": "#e46b74"}]
        items = []
        if self._message:
            items.append({
                "title": "Latest operation",
                "detail": self._message,
                "color": "#68a4ff",
            })
        items.append({
            "title": self.currentCaseTitle or "No investigation selected",
            "detail": "Current investigation" if self.currentCaseTitle else "Open a case to use case-specific tools",
            "color": "#68a4ff" if self.currentCaseTitle else "#8094a8",
        })
        if page in {"graph", "timeline", "entities", "evidence", "reports"}:
            items.append({"title": "Case-scoped data" if self.currentCaseTitle else "All stored data", "detail": "Loaded through the existing workspace service", "color": "#36cfa1"})
        if page == "osint":
            items.append({"title": "Collection form required", "detail": "Use an investigation workspace before running connectors", "color": "#e5a84b"})
        return items

    def _case_record(self, case: dict[str, Any]) -> dict[str, Any]:
        selected = str(case.get("id") or "") == self._current_case_id
        return {
            "id": str(case.get("id") or ""),
            "title": str(case.get("title") or "Untitled investigation"),
            "detail": str(case.get("description") or "No description"),
            "status": "Selected" if selected else "Active",
            "meta": self._short_id(case.get("id")),
            "color": "#36cfa1" if selected else "#68a4ff",
            "tint": "#12362f" if selected else "#142b47",
        }

    def _workspace_record(self, kind: str, item: dict[str, Any]) -> dict[str, Any]:
        if kind == "entities":
            confidence = item.get("confidence")
            detail = str(item.get("type") or "entity").replace("_", " ").title()
            meta = f"{float(confidence) * 100:.0f}%" if confidence is not None else ""
            title = item.get("value")
            status = "Entity"
        elif kind == "evidence":
            title = item.get("title")
            detail = item.get("description") or item.get("value") or "No preview available"
            status = str(item.get("type") or "evidence").replace("_", " ").title()
            meta = "SHA-256" if item.get("sha256") else ""
        elif kind == "reports":
            title = item.get("title")
            detail = item.get("description") or "Stored investigation report"
            status = str(item.get("type") or "report").replace("_", " ").title()
            meta = self._date_text(item.get("updated_at") or item.get("created_at"))
        else:
            title = item.get("title")
            detail = item.get("description") or "Investigation event"
            status = str(item.get("type") or "event").replace("_", " ").title()
            meta = str(item.get("date") or "")
        return {
            "id": str(item.get("id") or ""),
            "title": str(title or "Untitled record"),
            "detail": str(detail),
            "status": str(status),
            "meta": str(meta),
            "color": "#68a4ff",
            "tint": "#142b47",
        }

    def _run_osint_workspace_fallback(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
    ) -> bool:
        """Compatibility path for light-weight test/adaptor containers."""
        field = {
            OsintTargetType.EMAIL: "emails",
            OsintTargetType.USERNAME: "usernames",
            OsintTargetType.DOMAIN: "domains",
            OsintTargetType.IP: "ip_addresses",
            OsintTargetType.URL: "urls",
            OsintTargetType.PHONE: "phones",
        }.get(target_type)
        if field is None:
            self._set_message("Unsupported OSINT target type.")
            return False

        form_data: dict[str, Any] = {field: [value]}
        if self._current_case_id:
            form_data["case_id"] = self._current_case_id

        started_at = datetime.now()
        started_perf = perf_counter()
        try:
            result = self._container.osint_controller.run_investigation(
                form_data,
                timeout=30,
                use_cache=True,
                save_raw_output=False,
                include_metadata=True,
                include_related=True,
            )
        except Exception as exc:
            LOGGER.exception("OSINT collection failed")
            self._osint_run = self._failed_osint_run_payload(
                target_type=target_type,
                value=value,
                started_at=started_at,
                duration=perf_counter() - started_perf,
                error=str(exc),
            )
            self._set_message(f"OSINT collection failed: {exc}")
            self._generation += 1
            self.changed.emit()
            return False

        self._osint_run = self._build_workspace_run_payload(
            result=result if isinstance(result, dict) else {},
            target_type=target_type,
            value=value,
            started_at=started_at,
            duration=perf_counter() - started_perf,
        )
        summary = self._osint_run.get("summary", {})
        self._set_message(
            "OSINT collection completed; "
            f"{int(summary.get('findings') or 0)} finding(s) returned."
        )
        self._generation += 1
        self.changed.emit()
        return True

    def _build_enrichment_snapshot_run_payload(
        self,
        *,
        snapshot: dict[str, Any],
        target_type: OsintTargetType,
        value: str,
        started_at: datetime,
        duration: float,
        case_id: str,
        case_title: str,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        leads: list[dict[str, Any]] = []
        connectors: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        entities_by_id: dict[str, dict[str, Any]] = {}
        evidence_by_id: dict[str, dict[str, Any]] = {}

        executions = list(snapshot.get("executions") or [])
        for execution_index, execution in enumerate(executions):
            if not isinstance(execution, dict):
                continue
            goal = str(execution.get("goal") or "")
            execution_status = str(execution.get("status") or "unknown")
            execution_error = str(execution.get("error") or "").strip()
            records = list(execution.get("records") or [])

            if execution_error and not records:
                errors.append({
                    "id": f"execution:{execution_index}",
                    "title": goal.replace("_", " ").title() or "OSINT execution",
                    "detail": execution_error,
                    "status": execution_status.replace("_", " ").title(),
                    "meta": "Execution",
                    "color": "#f25d68",
                    "tint": "#3a1e26",
                })

            for record_index, record in enumerate(records):
                if not isinstance(record, dict):
                    continue
                status = str(record.get("status") or "unknown")
                connector_name = str(
                    record.get("runtimeConnectorName")
                    or record.get("connector")
                    or record.get("capabilityDisplayName")
                    or record.get("capabilityModule")
                    or "Unknown connector"
                )
                result_findings = list(record.get("findings") or [])

                finding_count = 0
                lead_count = 0
                for finding_index, finding in enumerate(result_findings):
                    if not isinstance(finding, dict):
                        continue
                    metadata = finding.get("metadata")
                    is_lead = bool(
                        isinstance(metadata, dict)
                        and metadata.get("lead_only", False)
                    )
                    row = self._serialized_osint_finding_row(
                        finding=finding,
                        connector=connector_name,
                        goal=goal,
                        row_id=(
                            f"{execution_index}:{record_index}:{finding_index}"
                        ),
                        is_lead=is_lead,
                    )
                    if is_lead:
                        lead_count += 1
                        leads.append(row)
                    else:
                        finding_count += 1
                        findings.append(row)

                result_error = str(record.get("error") or "").strip()
                execution_time = self._safe_float(record.get("executionTime"))
                connector_color, connector_tint = self._osint_status_colors(status)
                connectors.append({
                    "id": f"{execution_index}:{record_index}:{connector_name}",
                    "name": connector_name,
                    "title": connector_name,
                    "detail": (
                        goal.replace("_", " ").title()
                        if goal
                        else "OSINT connector"
                    ),
                    "goal": goal,
                    "status": status,
                    "statusLabel": status.replace("_", " ").title(),
                    "findingCount": finding_count,
                    "leadCount": lead_count,
                    "itemCount": len(result_findings),
                    "executionTime": execution_time,
                    "meta": f"{execution_time:.1f}s",
                    "error": result_error,
                    "color": connector_color,
                    "tint": connector_tint,
                })

                if result_error:
                    errors.append({
                        "id": f"connector:{execution_index}:{record_index}",
                        "title": connector_name,
                        "detail": result_error,
                        "status": status.replace("_", " ").title(),
                        "meta": goal.replace("_", " ").title(),
                        "color": "#f25d68",
                        "tint": "#3a1e26",
                    })

        for persistence in list(snapshot.get("persistences") or []):
            if not isinstance(persistence, dict):
                continue
            for persisted in list(persistence.get("persisted") or []):
                if not isinstance(persisted, dict):
                    continue
                evidence = persisted.get("evidence")
                if isinstance(evidence, dict):
                    evidence_id = str(evidence.get("id") or "")
                    if evidence_id and evidence_id not in evidence_by_id:
                        evidence_type_text = str(evidence.get("type") or "evidence")
                        evidence_by_id[evidence_id] = {
                            "id": evidence_id,
                            "title": str(
                                evidence.get("title")
                                or evidence.get("value")
                                or "Evidence"
                            ),
                            "detail": str(
                                evidence.get("value")
                                or "Persisted OSINT evidence"
                            ),
                            "status": evidence_type_text.replace("_", " ").title(),
                            "meta": "Persisted",
                            "color": "#68a4ff",
                            "tint": "#142b47",
                        }

                for entity in list(persisted.get("entities") or []):
                    if not isinstance(entity, dict):
                        continue
                    entity_id = str(entity.get("id") or "")
                    if not entity_id or entity_id in entities_by_id:
                        continue
                    entity_type_text = str(entity.get("type") or "entity")
                    confidence = self._safe_optional_float(
                        entity.get("confidence")
                    )
                    entities_by_id[entity_id] = {
                        "id": entity_id,
                        "title": str(entity.get("value") or "Unnamed entity"),
                        "detail": entity_type_text.replace("_", " ").title(),
                        "status": "Entity",
                        "meta": self._confidence_text(confidence),
                        "confidence": confidence,
                        "color": "#a98be9",
                        "tint": "#271f43",
                    }

        status_counts = Counter(
            str(item.get("status") or "unknown") for item in connectors
        )
        success_like = status_counts.get("success", 0) + status_counts.get("partial", 0)
        if success_like:
            run_status = "completed_with_errors" if errors else "completed"
        elif connectors or errors:
            run_status = "failed"
        else:
            run_status = "completed"

        counts = snapshot.get("counts")
        if not isinstance(counts, dict):
            counts = {}

        completed_at = datetime.now()
        return {
            "hasRun": True,
            "status": run_status,
            "targetType": target_type.value,
            "targetValue": value,
            "caseId": case_id,
            "caseTitle": case_title,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "completedAt": completed_at.isoformat(timespec="seconds"),
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "summary": {
                "connectors": len(connectors),
                "successful": status_counts.get("success", 0),
                "partial": status_counts.get("partial", 0),
                "failed": status_counts.get("failed", 0),
                "unavailable": status_counts.get("not_available", 0),
                "notSupported": status_counts.get("not_supported", 0),
                "findings": len(findings),
                "leads": len(leads),
                "errors": len(errors),
                "persistedFindings": int(counts.get("persistedFindings") or 0),
                "sourcesCreated": int(counts.get("sourcesCreated") or 0),
                "evidenceCreated": int(counts.get("evidenceCreated") or 0),
                "entitiesCreated": int(counts.get("entitiesCreated") or 0),
                "linksCreated": int(counts.get("linksCreated") or 0),
            },
            "findings": findings,
            "leads": leads,
            "entities": list(entities_by_id.values()),
            "evidence": list(evidence_by_id.values()),
            "connectors": connectors,
            "errors": errors,
        }


    def _build_workspace_run_payload(
        self,
        *,
        result: dict[str, Any],
        target_type: OsintTargetType,
        value: str,
        started_at: datetime,
        duration: float,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        leads: list[dict[str, Any]] = []
        connectors: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for target_index, target_result in enumerate(result.get("target_results") or []):
            if not isinstance(target_result, dict):
                continue
            for result_index, connector_result in enumerate(
                target_result.get("results") or []
            ):
                if not isinstance(connector_result, dict):
                    continue
                connector_name = str(
                    connector_result.get("connector") or "Unknown connector"
                )
                status = str(connector_result.get("status") or "unknown")
                result_findings = list(connector_result.get("findings") or [])
                finding_count = 0
                lead_count = 0

                for finding_index, finding in enumerate(result_findings):
                    if not isinstance(finding, dict):
                        continue
                    is_lead = str(finding.get("kind") or "finding") == "lead"
                    row = self._serialized_osint_finding_row(
                        finding=finding,
                        connector=connector_name,
                        goal="",
                        row_id=f"{target_index}:{result_index}:{finding_index}",
                        is_lead=is_lead,
                    )
                    if is_lead:
                        lead_count += 1
                        leads.append(row)
                    else:
                        finding_count += 1
                        findings.append(row)

                error = str(connector_result.get("error") or "").strip()
                execution_time = self._safe_float(
                    connector_result.get("execution_time")
                )
                color, tint = self._osint_status_colors(status)
                connectors.append({
                    "id": f"{target_index}:{result_index}:{connector_name}",
                    "name": connector_name,
                    "title": connector_name,
                    "detail": "OSINT connector",
                    "goal": "",
                    "status": status,
                    "statusLabel": status.replace("_", " ").title(),
                    "findingCount": finding_count,
                    "leadCount": lead_count,
                    "itemCount": len(result_findings),
                    "executionTime": execution_time,
                    "meta": f"{execution_time:.1f}s",
                    "error": error,
                    "color": color,
                    "tint": tint,
                })
                if error:
                    errors.append({
                        "id": f"connector:{target_index}:{result_index}",
                        "title": connector_name,
                        "detail": error,
                        "status": status.replace("_", " ").title(),
                        "meta": "Connector",
                        "color": "#f25d68",
                        "tint": "#3a1e26",
                    })

        status_counts = Counter(
            str(item.get("status") or "unknown") for item in connectors
        )
        success_like = status_counts.get("success", 0) + status_counts.get("partial", 0)
        run_status = (
            "completed_with_errors"
            if success_like and errors
            else "completed"
            if success_like or not errors
            else "failed"
        )
        completed_at = datetime.now()
        return {
            "hasRun": True,
            "status": run_status,
            "targetType": target_type.value,
            "targetValue": value,
            "caseId": str(result.get("case_id") or self._current_case_id),
            "caseTitle": self.currentCaseTitle,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "completedAt": completed_at.isoformat(timespec="seconds"),
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "summary": {
                "connectors": len(connectors),
                "successful": status_counts.get("success", 0),
                "partial": status_counts.get("partial", 0),
                "failed": status_counts.get("failed", 0),
                "unavailable": status_counts.get("not_available", 0),
                "notSupported": status_counts.get("not_supported", 0),
                "findings": len(findings),
                "leads": len(leads),
                "errors": len(errors),
                "persistedFindings": 0,
                "sourcesCreated": 0,
                "evidenceCreated": 0,
                "entitiesCreated": 0,
                "linksCreated": 0,
            },
            "findings": findings,
            "leads": leads,
            "entities": [],
            "evidence": [],
            "connectors": connectors,
            "errors": errors,
        }

    def _running_osint_run_payload(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        started_at: datetime,
        case_id: str,
        case_title: str,
    ) -> dict[str, Any]:
        return {
            "hasRun": True,
            "status": "running",
            "targetType": target_type.value,
            "targetValue": value,
            "caseId": case_id,
            "caseTitle": case_title,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "completedAt": "",
            "durationSeconds": 0.0,
            "durationText": "Running…",
            "summary": {
                "connectors": 0,
                "successful": 0,
                "partial": 0,
                "failed": 0,
                "unavailable": 0,
                "notSupported": 0,
                "findings": 0,
                "leads": 0,
                "errors": 0,
                "persistedFindings": 0,
                "sourcesCreated": 0,
                "evidenceCreated": 0,
                "entitiesCreated": 0,
                "linksCreated": 0,
            },
            "findings": [],
            "leads": [],
            "entities": [],
            "evidence": [],
            "connectors": [],
            "errors": [],
        }

    def _failed_osint_run_payload(
        self,
        *,
        target_type: OsintTargetType,
        value: str,
        started_at: datetime,
        duration: float,
        error: str,
    ) -> dict[str, Any]:
        completed_at = datetime.now()
        return {
            "hasRun": True,
            "status": "failed",
            "targetType": target_type.value,
            "targetValue": value,
            "caseId": self._current_case_id,
            "caseTitle": self.currentCaseTitle,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "completedAt": completed_at.isoformat(timespec="seconds"),
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "summary": {
                "connectors": 0,
                "successful": 0,
                "partial": 0,
                "failed": 1,
                "unavailable": 0,
                "notSupported": 0,
                "findings": 0,
                "leads": 0,
                "errors": 1,
                "persistedFindings": 0,
                "sourcesCreated": 0,
                "evidenceCreated": 0,
                "entitiesCreated": 0,
                "linksCreated": 0,
            },
            "findings": [],
            "leads": [],
            "entities": [],
            "evidence": [],
            "connectors": [],
            "errors": [{
                "id": "run:error",
                "title": "Collection failed",
                "detail": error or "Unknown OSINT error",
                "status": "Failed",
                "meta": "Run",
                "color": "#f25d68",
                "tint": "#3a1e26",
            }],
        }

    def _osint_finding_row(
        self,
        *,
        finding: Any,
        connector: str,
        goal: str,
        row_id: str,
    ) -> dict[str, Any]:
        metadata = getattr(finding, "metadata", None)
        is_lead = bool(
            isinstance(metadata, dict) and metadata.get("lead_only", False)
        )
        serialized = {
            "category": getattr(finding, "category", None),
            "value": getattr(finding, "value", None),
            "confidence": getattr(finding, "confidence", None),
            "source": getattr(finding, "source", None),
            "url": getattr(finding, "url", None),
            "reliability": getattr(finding, "reliability", None),
        }
        return self._serialized_osint_finding_row(
            finding=serialized,
            connector=connector,
            goal=goal,
            row_id=row_id,
            is_lead=is_lead,
        )

    def _serialized_osint_finding_row(
        self,
        *,
        finding: dict[str, Any],
        connector: str,
        goal: str,
        row_id: str,
        is_lead: bool,
    ) -> dict[str, Any]:
        category = str(finding.get("category") or "finding")
        value = str(finding.get("value") or "").strip()
        source = str(finding.get("source") or "").strip()
        url = str(finding.get("url") or "").strip()
        confidence = self._safe_optional_float(finding.get("confidence"))
        reliability = self._safe_optional_float(finding.get("reliability"))
        detail_parts = [part for part in (source, connector) if part]
        color = "#f4b638" if is_lead else "#68a4ff"
        tint = "#3b3015" if is_lead else "#142b47"
        return {
            "id": row_id,
            "kind": "lead" if is_lead else "finding",
            "title": value or category.replace("_", " ").title(),
            "detail": " · ".join(detail_parts) or "OSINT result",
            "status": category.replace("_", " ").title(),
            "meta": self._confidence_text(confidence),
            "category": category,
            "value": value,
            "source": source,
            "url": url,
            "connector": connector,
            "goal": goal,
            "confidence": confidence,
            "reliability": reliability,
            "color": color,
            "tint": tint,
        }

    def _invalidate_after_osint(self) -> None:
        session = getattr(self._container, "session", None)
        if session is not None:
            try:
                session.expire_all()
            except Exception:
                LOGGER.debug("Unable to expire GUI session after OSINT", exc_info=True)

        self._workspaces.pop(self._current_case_id, None)
        for page in ("entities", "evidence", "timeline"):
            self._page_records.pop(page, None)
            self._page_offsets.pop(page, None)
            self._page_errors.pop(page, None)
            self._page_totals.pop(page, None)

        case_id = UUID(self._current_case_id) if self._current_case_id else None
        for page, attr in (
            ("entities", "entity_service"),
            ("evidence", "evidence_service"),
            ("timeline", "timeline_service"),
        ):
            service = getattr(self._container, attr, None)
            if service is None:
                continue
            try:
                self._page_totals[page] = int(
                    service.count_all(case_id=case_id)
                )
            except Exception:
                LOGGER.debug(
                    "Unable to refresh %s count after OSINT",
                    page,
                    exc_info=True,
                )

    @staticmethod
    def _osint_status_colors(status: str) -> tuple[str, str]:
        normalized = str(status or "").strip().lower()
        if normalized == "success":
            return "#45d898", "#12362f"
        if normalized == "partial":
            return "#f4b638", "#3b3015"
        if normalized in {"failed", "error"}:
            return "#f25d68", "#3a1e26"
        if normalized in {"not_available", "not_supported", "skipped"}:
            return "#8094a8", "#1a2b37"
        return "#68a4ff", "#142b47"

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _confidence_text(value: float | None) -> str:
        if value is None:
            return ""
        return f"{max(0.0, min(1.0, value)) * 100:.0f}%"

    def _connector_records(self) -> list[dict[str, Any]]:
        if self._connector_cache is not None:
            return self._connector_cache
        try:
            state = self._container.osint_controller.get_workspace_state() or {}
            connectors = state.get("connectors") or []
        except Exception as exc:
            LOGGER.exception("Unable to load OSINT connector state")
            self._set_message(f"Unable to load connector state: {exc}")
            connectors = []
        records = [
            {"id": str(name), "title": str(name), "detail": "Registered OSINT connector", "status": "Available", "meta": "Pipeline", "color": "#36cfa1", "tint": "#12362f"}
            for name in connectors
        ]
        self._connector_cache = records
        LOGGER.info("[OSINT] initial=True scope=registry model_rows=%s has_more=False loading=False", len(records))
        return records

    def _recent_intelligence(self, entities: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[tuple[str, dict[str, Any]]] = []
        for item in entities:
            rows.append((str(item.get("created_at") or item.get("updated_at") or ""), {
                "headline": str(item.get("value") or "Unnamed entity"),
                "detail": f"{str(item.get('type') or 'entity').replace('_', ' ').title()} added to an investigation",
                "timeText": self._date_text(item.get("created_at") or item.get("updated_at")),
                "icon": "users_purple.svg",
                "color": "#a98be9",
            }))
        for item in evidence:
            rows.append((str(item.get("created_at") or item.get("updated_at") or ""), {
                "headline": str(item.get("title") or "Untitled evidence"),
                "detail": f"{str(item.get('type') or 'evidence').replace('_', ' ').title()} evidence recorded",
                "timeText": self._date_text(item.get("created_at") or item.get("updated_at")),
                "icon": "document_blue.svg",
                "color": "#68a4ff",
            }))
        rows.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _, row in rows]

    def _all_workspace_items(self, key: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for workspace in self._workspaces.values():
            result.extend(item for item in (workspace.get(key) or []) if isinstance(item, dict))
        return result

    def _selected_or_all(self, key: str) -> list[dict[str, Any]]:
        workspace = self._current_workspace()
        if workspace:
            return [item for item in (workspace.get(key) or []) if isinstance(item, dict)]
        return self._all_workspace_items(key)

    def _type_count(self, key: str) -> int:
        return len(Counter(str(item.get("type") or "") for item in self._selected_or_all(key) if item.get("type")))

    def _current_workspace(self) -> dict[str, Any]:
        return self._workspaces.get(self._current_case_id, {})

    def _case_by_id(self, case_id: str) -> dict[str, Any] | None:
        return next((case for case in self._cases if str(case.get("id") or "") == case_id), None)

    def _set_message(self, message: str) -> None:
        normalized = str(message or "")
        if normalized != self._message:
            self._message = normalized
            self.messageChanged.emit()

    @staticmethod
    def _greeting() -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning."
        if hour < 18:
            return "Good afternoon."
        return "Good evening."

    @staticmethod
    def _dashboard_summary(case_count: int, intelligence_count: int) -> str:
        if not case_count:
            return "No active investigations. Create a case to begin analysis."
        suffix = f" and {intelligence_count} recent intelligence item(s)" if intelligence_count else ""
        return f"{case_count} active investigation(s){suffix}."

    @staticmethod
    def _empty_text(page: str, filtered: bool) -> str:
        if filtered:
            return "No records match the current filter."
        return {
            "cases": "No active investigations",
            "search": "Enter a query to search stored intelligence",
            "entities": "No entities yet",
            "graph": "Select a case with entities to view its graph",
            "timeline": "No timeline events yet",
            "osint": "No OSINT connectors are registered",
            "evidence": "No evidence yet",
            "reports": "No reports yet",
            "settings": "No settings interface existed in the previous application",
        }.get(page, "No records available")

    @staticmethod
    def _disabled_reason(page: str) -> str:
        return {
            "search": "Use the search field; a separate New Search action did not exist.",
            "entities": "Entity creation requires source context in the existing workspace.",
            "graph": "Saved graph creation did not exist in the previous application.",
            "timeline": "Timeline creation requires source context in the existing workspace.",
            "evidence": "Evidence creation requires source context in the existing workspace.",
            "reports": "Report creation requires an open investigation workspace.",
            "settings": "No settings action existed in the previous application.",
        }.get(page, "This action is unavailable.")

    @staticmethod
    def _short_id(value: Any) -> str:
        text = str(value or "")
        return text[:8] if text else ""

    @staticmethod
    def _date_text(value: Any) -> str:
        if not value:
            return ""
        text = str(value)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            return text[:16]

    @staticmethod
    def _score_text(value: Any) -> str:
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return ""
