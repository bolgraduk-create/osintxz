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

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.investigation.search_query import InvestigationSearchQuery, SearchMethod


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
        self.refresh()
        self._set_message("Investigation deleted.")
        return True

    @Slot(str, str, result=bool)
    def runOsint(self, target_type: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if not normalized_value:
            self._set_message("OSINT collection requires a target.")
            return False
        field = {
            "email": "emails",
            "username": "usernames",
            "domain": "domains",
            "ip": "ip_addresses",
            "url": "urls",
            "phone": "phones",
        }.get(str(target_type or "").strip().lower())
        if field is None:
            self._set_message("Unsupported OSINT target type.")
            return False
        form_data: dict[str, Any] = {field: [normalized_value]}
        if self._current_case_id:
            form_data["case_id"] = self._current_case_id
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
            self._set_message(f"OSINT collection failed: {exc}")
            return False
        target_count = int((result or {}).get("target_count") or 1)
        finding_count = int(
            (result or {}).get("finding_count")
            or (result or {}).get("total_findings")
            or 0
        )
        self._set_message(
            f"OSINT collection completed for {target_count} target(s); "
            f"{finding_count} finding(s) returned."
        )
        self._generation += 1
        self.changed.emit()
        return True

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
