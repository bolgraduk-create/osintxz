"""Backend-backed view model for the authoritative QML desktop shell.

The bridge deliberately contains presentation mapping only. Database access and
business operations stay in the existing controllers and application services.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import logging
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from PySide6.QtCore import QObject, Property, QSettings, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from app.application.person_attachment_service import PersonAttachmentService
from app.application.person_profile_selection_service import PersonProfileSelectionService
from app.application.person_identity_review_service import (
    IdentityReviewDecision,
    PersonIdentityReviewService,
)
from app.application.identity_relationship_corroboration import (
    IdentityRelationshipCorroborationService,
)
from app.application.identity_confidence_calibration import (
    IdentityConfidenceCalibrationService,
)
from app.application.identity_resolution import IdentityResolution
from app.application.unified_target_profile import build_unified_target_profile
from app.investigation.search_query import InvestigationSearchQuery, SearchMethod
from app.models.entity import EntityType
from app.interface.desktop.workers import (
    OsintCollectionWorker,
    RegistrySearchWorker,
)
from app.osint.models import OsintTargetType


LOGGER = logging.getLogger(__name__)


class DesktopBridge(QObject):
    """Expose existing OSINTXZ application services to QML."""

    changed = Signal()
    navigationRequested = Signal(str)
    messageChanged = Signal()
    PAGE_SIZE = 100
    ENTITY_CATEGORY_TYPES: dict[str, tuple[EntityType, ...]] = {
        # The user-facing Entity Directory is a PERSON directory. Technical
        # entities remain persisted for evidence, graph, pivots and analysis.
        "all": (EntityType.PERSON,),
        "people": (EntityType.PERSON,),
        "organizations": (EntityType.ORGANIZATION,),
        "profiles": (EntityType.USERNAME, EntityType.ACCOUNT),
        "links": (EntityType.URL, EntityType.DOMAIN),
        "contacts": (EntityType.EMAIL, EntityType.PHONE),
        "network": (EntityType.IP,),
        "locations": (EntityType.LOCATION, EntityType.ADDRESS),
        "documents": (EntityType.DOCUMENT,),
        "other": (EntityType.VEHICLE, EntityType.OTHER),
    }
    NAVIGATION_PAGES = {
        "overview", "cases", "search", "registry", "entities", "person",
        "graph", "timeline", "analysis", "osint", "evidence", "reports", "report", "settings",
    }

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._cases: list[dict[str, Any]] = []
        self._workspaces: dict[str, dict[str, Any]] = {}
        self._current_case_id = ""
        self._search_results: list[dict[str, Any]] = []
        self._entity_category = "all"
        self._entity_type_counts: dict[str, int] = {}
        self._current_entity_id = ""
        self._current_entity_snapshot: dict[str, Any] = {}
        self._current_report_id = ""
        self._current_report_snapshot: dict[str, Any] = {}
        self._workspace_focus_page = ""
        self._workspace_focus_id = ""
        self._avatar_cache: dict[str, str] = {}
        self._graph_focus_entity_id = ""
        self._desktop_settings = QSettings("OSINTXZ", "OSINTXZ")
        self._dashboard_focus_entity_id = ""
        self._dashboard_graph_depth = 1
        self._dashboard_path_start_id = ""
        self._dashboard_path_end_id = ""
        self._osint_run: dict[str, Any] = {}
        self._osint_busy = False
        self._osint_thread: QThread | None = None
        self._osint_worker: OsintCollectionWorker | None = None
        self._osint_context: dict[str, Any] = {}
        self._registry_run: dict[str, Any] = {}
        self._registry_busy = False
        self._registry_thread: QThread | None = None
        self._registry_worker: RegistrySearchWorker | None = None
        self._registry_context: dict[str, Any] = {}
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

    @Property(str, notify=changed)
    def entityCategory(self) -> str:
        return self._entity_category

    @Property("QVariantMap", notify=changed)
    def entityCategoryCounts(self) -> dict[str, int]:
        return self._entity_category_counts()

    @Property("QVariantMap", notify=changed)
    def currentEntity(self) -> dict[str, Any]:
        return dict(self._current_entity_snapshot)

    @Property("QVariantMap", notify=changed)
    def currentReport(self) -> dict[str, Any]:
        return dict(self._current_report_snapshot)

    @Property("QVariantMap", notify=changed)
    def uiSettings(self) -> dict[str, Any]:
        return self._ui_settings_payload()

    @Property("QVariantMap", notify=changed)
    def graphWorkspace(self) -> dict[str, Any]:
        return self._graph_workspace_payload()

    @Property("QVariantMap", notify=changed)
    def workspaceFocus(self) -> dict[str, str]:
        return {
            "page": self._workspace_focus_page,
            "id": self._workspace_focus_id,
        }

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
    def registryRun(self) -> dict[str, Any]:
        return dict(self._registry_run)

    @Property(bool, notify=changed)
    def registryBusy(self) -> bool:
        return self._registry_busy

    @Property("QVariantMap", notify=changed)
    def dashboard(self) -> dict[str, Any]:
        entities = self._all_workspace_items("entities")
        evidence = self._all_workspace_items("evidence")
        recent_cases = [self._case_record(case) for case in self._cases[:4]]
        intelligence = self._recent_intelligence(entities, evidence)
        graph = self._dashboard_graph_payload()
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
            "graphNodes": graph["nodes"],
            "graphEdges": graph["edges"],
            "graphOptions": graph["options"],
            "graphFocusId": graph["focusId"],
            "graphNotice": graph["notice"],
            "graphCaseTitle": self.currentCaseTitle,
            "graphDepth": graph["depth"],
            "graphPathStartId": graph["pathStartId"],
            "graphPathEndId": graph["pathEndId"],
            "graphPathFound": graph["pathFound"],
            "graphPathLabel": graph["pathLabel"],
            "personSummary": graph.get("summary", []),
            "graphPersonTitle": graph.get("personTitle", ""),
            "graphAccountCount": graph.get("accountCount", 0),
        }

    @Slot()
    def refresh(self) -> None:
        """Reload UI data exclusively through existing controllers/services."""
        started = perf_counter()
        try:
            cases = self._container.case_controller.get_cases() or []
            self._cases = [dict(case) for case in cases if isinstance(case, dict)]
            self._workspaces = {}
            self._avatar_cache.clear()
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
                self._current_entity_id = ""
                self._current_entity_snapshot = {}
                self._current_report_id = ""
                self._current_report_snapshot = {}
                self._graph_focus_entity_id = ""
            self._refresh_entity_type_counts()
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
        action_enabled = (
            page_key in {"cases", "osint"}
            or (
                page_key == "entities"
                and bool(self._current_case_id)
            )
        )
        action_reason = ""
        if not action_enabled:
            if page_key == "entities" and not self._current_case_id:
                action_reason = "Select an investigation before adding a person."
            else:
                action_reason = self._disabled_reason(page_key)

        result = {
            "metrics": self._metrics_for_page(page_key),
            "records": records,
            "contextItems": self._context_for_page(page_key),
            "emptyText": self._page_errors.get(page_key) or self._empty_text(page_key, bool(normalized_query)),
            "actionEnabled": action_enabled,
            "actionReason": action_reason,
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
                if page == "entities":
                    allowed = {item.value for item in self._entity_types_for_category(self._entity_category)}
                    if allowed:
                        items = [
                            item for item in items
                            if str(item.get("type") or item.get("entity_type") or "").strip().lower() in allowed
                        ]
                rows = items[offset:offset + self.PAGE_SIZE]
                total = len(items)
                mapped = [self._workspace_record(page, row) for row in rows]
            else:
                case_id = UUID(self._current_case_id) if self._current_case_id else None
                if page == "entities":
                    entity_types = self._entity_types_for_category(self._entity_category)

                    # Keep the unfiltered ("All") path compatible with the
                    # long-standing EntityService paging contract.  The
                    # entity_types keyword is an M022.3E extension and should
                    # only be sent when an actual category filter is active.
                    # This also keeps lightweight/legacy service doubles usable
                    # without weakening filtered production queries.
                    if entity_types:
                        rows = svc.get_page(
                            limit=self.PAGE_SIZE,
                            offset=offset,
                            case_id=case_id,
                            entity_types=entity_types,
                        )
                        total = (
                            svc.count_all(
                                case_id=case_id,
                                entity_types=entity_types,
                            )
                            if offset == 0
                            else self._page_totals[page]
                        )
                    else:
                        rows = svc.get_page(
                            limit=self.PAGE_SIZE,
                            offset=offset,
                            case_id=case_id,
                        )
                        total = (
                            svc.count_all(case_id=case_id)
                            if offset == 0
                            else self._page_totals[page]
                        )
                else:
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
        for key in (
            "id", "case_id", "title", "description", "value", "normalized_value",
            "type", "confidence", "metadata_json", "sha256", "source_id",
            "created_at", "updated_at", "event_time", "date", "content",
        ):
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
            self._current_entity_id = ""
            self._current_entity_snapshot = {}
            self._current_report_id = ""
            self._current_report_snapshot = {}
            self._workspace_focus_page = ""
            self._workspace_focus_id = ""
            self._graph_focus_entity_id = ""
            self._dashboard_focus_entity_id = ""
            self._dashboard_path_start_id = ""
            self._dashboard_path_end_id = ""
            self._avatar_cache.clear()
        self._current_case_id = normalized
        self._refresh_entity_type_counts()
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

    @Slot(str, str, result="QVariantMap")
    def createPerson(
        self,
        name: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a distinct PERSON in the currently selected investigation."""

        if not self._current_case_id:
            return {
                "ok": False,
                "error": "Select an investigation before adding a person.",
            }

        normalized_name = " ".join(
            str(name or "")
            .strip()
            .split()
        )

        if not normalized_name:
            return {
                "ok": False,
                "error": "Person name cannot be empty.",
            }

        if len(normalized_name) > 255:
            return {
                "ok": False,
                "error": "Person name is too long.",
            }

        entity_service = getattr(
            self._container,
            "entity_service",
            None,
        )
        if entity_service is None:
            return {
                "ok": False,
                "error": "Entity service is unavailable.",
            }

        try:
            person = entity_service.create_entity(
                case_id=UUID(self._current_case_id),
                entity_type=EntityType.PERSON,
                value=normalized_name,
                confidence=1.0,
                metadata_json=json.dumps(
                    {
                        "workflow": "manual_person_creation",
                        "analyst_created": True,
                        "identity_verified": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                description=str(
                    description
                    or ""
                ).strip(),
            )
            self._container.commit()
        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug(
                    "Rollback after PERSON creation failed",
                    exc_info=True,
                )
            LOGGER.exception(
                "Unable to create PERSON"
            )
            return {
                "ok": False,
                "error": str(exc),
            }

        self._page_records.pop(
            "entities",
            None,
        )
        self._page_offsets.pop(
            "entities",
            None,
        )
        self._page_totals.pop(
            "entities",
            None,
        )
        self._page_errors.pop(
            "entities",
            None,
        )
        self._refresh_entity_type_counts()
        self._load_page(
            "entities",
            0,
            notify=False,
        )
        self._set_message(
            "Person created."
        )
        self._generation += 1
        self.changed.emit()

        return {
            "ok": True,
            "id": str(person.id),
            "label": str(person.value),
            "message": "Person created.",
        }

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
            self._current_entity_id = ""
            self._current_entity_snapshot = {}
            self._dashboard_focus_entity_id = ""
            self._avatar_cache.clear()
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
            "hash": OsintTargetType.HASH,
        }.get(normalized_type)
        if target_enum is None:
            self._set_message("Unsupported OSINT target type.")
            return False

        # Test/adaptor containers can still expose only the older workspace
        # controller. Production uses the bounded recursive M021 boundary.
        recursive_service = getattr(
            self._container,
            "osint_recursive_enrichment_service",
            None,
        )
        if recursive_service is None:
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
            worker.progress.connect(self._on_osint_worker_progress)
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
    def _on_osint_worker_progress(self, result: object) -> None:
        """Expose truthful target-level recursive progress to the QML run view."""
        context = dict(self._osint_context)
        if not context:
            return

        # Never surface progress from a background run in another case.
        if self._current_case_id != str(context.get("caseId") or ""):
            return

        progress = result if isinstance(result, dict) else {}
        current = dict(self._osint_run)
        if not current:
            return

        normalized_progress = {
            "phase": str(progress.get("phase") or ""),
            "targetType": str(progress.get("targetType") or ""),
            "targetValue": str(progress.get("targetValue") or ""),
            "depth": progress.get("depth"),
            "targetsProcessed": int(progress.get("targetsProcessed") or 0),
            "queuedTargets": int(progress.get("queuedTargets") or 0),
            "candidatesDiscovered": int(
                progress.get("candidatesDiscovered") or 0
            ),
            "candidatesEnqueued": int(progress.get("candidatesEnqueued") or 0),
            "newEntitiesCount": int(progress.get("newEntitiesCount") or 0),
            "persistedFindings": int(progress.get("persistedFindings") or 0),
            "entitiesCreated": int(progress.get("entitiesCreated") or 0),
            "elapsedSeconds": self._safe_float(progress.get("elapsedSeconds")),
            "stopReason": str(progress.get("stopReason") or ""),
        }

        current["progress"] = normalized_progress
        elapsed = normalized_progress["elapsedSeconds"]
        current["durationSeconds"] = round(elapsed, 3)
        current["durationText"] = f"{elapsed:.1f}s · Running…"

        summary = dict(current.get("summary") or {})
        summary["targetsProcessed"] = normalized_progress["targetsProcessed"]
        summary["queuedTargets"] = normalized_progress["queuedTargets"]
        summary["candidatesDiscovered"] = (
            normalized_progress["candidatesDiscovered"]
        )
        summary["candidatesEnqueued"] = normalized_progress["candidatesEnqueued"]
        summary["newEntitiesCount"] = normalized_progress["newEntitiesCount"]
        current["summary"] = summary
        self._osint_run = current

        target_value = normalized_progress["targetValue"]
        depth = normalized_progress["depth"]
        if target_value:
            depth_text = f" · depth {depth}" if depth is not None else ""
            self._set_message(
                "OSINT recursive collection running: "
                f"{target_value}{depth_text}. "
                f"{normalized_progress['targetsProcessed']} target(s) processed, "
                f"{normalized_progress['queuedTargets']} queued."
            )

        self._generation += 1
        self.changed.emit()

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
            "OSINT recursive collection completed across "
            f"{int(summary.get('targetsProcessed') or 0)} target(s); "
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

    @Slot()
    def openRegistry(self) -> None:
        self.navigationRequested.emit("registry")

    @Slot()
    def openOsint(self) -> None:
        self.navigationRequested.emit("osint")

    @Slot(str, result=bool)
    def navigateTo(self, page: str) -> bool:
        """Navigate only to a known desktop route."""

        normalized = str(page or "").strip().lower()
        if normalized not in self.NAVIGATION_PAGES:
            self._set_message("The requested page is unavailable.")
            return False
        self.navigationRequested.emit(normalized)
        return True

    @Slot(str, str, result=bool)
    def focusWorkspaceRecord(self, page: str, record_id: str) -> bool:
        """Open a data workspace and focus one authoritative stored record."""

        page_key = str(page or "").strip().lower()
        normalized_id = str(record_id or "").strip()
        if page_key not in {"evidence", "timeline"} or not normalized_id:
            return False

        service_name = {
            "evidence": "evidence_service",
            "timeline": "timeline_service",
        }[page_key]
        getter_name = {
            "evidence": "get_evidence",
            "timeline": "get_event",
        }[page_key]

        service = getattr(self._container, service_name, None)
        getter = getattr(service, getter_name, None) if service is not None else None
        if not callable(getter):
            self._set_message("The selected source workspace is unavailable.")
            return False

        try:
            row = getter(UUID(normalized_id))
        except Exception as exc:
            LOGGER.debug("Unable to resolve focused %s record", page_key, exc_info=True)
            self._set_message(f"Unable to open selected {page_key} source: {exc}")
            return False

        if row is None:
            self._set_message("The selected source record is unavailable.")
            return False

        row_case_id = str(getattr(row, "case_id", "") or "")
        if self._current_case_id and row_case_id and row_case_id != self._current_case_id:
            self._set_message("The selected source is outside the current investigation.")
            return False

        if page_key not in self._page_records:
            self._load_page(page_key, 0, notify=False)

        mapped = self._workspace_record(
            page_key,
            self._model_dict(row),
        )
        current = list(self._page_records.get(page_key, []))
        if not any(
            str(item.get("id") or "") == normalized_id
            for item in current
        ):
            current.insert(0, mapped)
            self._page_records[page_key] = current

        self._workspace_focus_page = page_key
        self._workspace_focus_id = normalized_id
        self._set_message(
            "Focused "
            + page_key.replace("_", " ")
            + " source "
            + normalized_id[:8]
            + "."
        )
        self._generation += 1
        self.changed.emit()
        self.navigationRequested.emit(page_key)
        return True

    @Slot(str, result=bool)
    def openCase(self, case_id: str) -> bool:
        """Select a dashboard case and open the Cases workspace."""

        if not self.selectCase(case_id):
            return False
        self.navigationRequested.emit("cases")
        return True

    @Slot(str, result=bool)
    def selectDashboardEntity(self, entity_id: str) -> bool:
        """Select the PERSON shown by the simplified Home intelligence card.

        Home is intentionally person-centric.  Cross-person/network exploration
        belongs to the dedicated Graph page.
        """

        normalized = str(entity_id or "").strip()
        if not normalized or not self._current_case_id:
            return False

        service = getattr(self._container, "entity_service", None)
        if service is not None:
            try:
                entity = service.get_entity(UUID(normalized))
            except Exception:
                LOGGER.debug("Unable to resolve dashboard PERSON focus", exc_info=True)
                return False
            if entity is None or str(getattr(entity, "case_id", "")) != self._current_case_id:
                return False
            entity_type = str(
                getattr(
                    getattr(entity, "entity_type", None),
                    "value",
                    getattr(entity, "entity_type", ""),
                )
                or ""
            ).strip().lower()
            if entity_type != EntityType.PERSON.value:
                return False
        else:
            workspace = self._current_workspace() or {}
            graph = workspace.get("graph", {}) or {}
            person_ids = {
                str(item.get("id") or "")
                for item in list(graph.get("nodes") or [])
                if str(item.get("type") or "").strip().lower() == EntityType.PERSON.value
            }
            if normalized not in person_ids:
                return False

        self._dashboard_focus_entity_id = normalized
        self._generation += 1
        self.changed.emit()
        return True

    @Slot(int, result=bool)
    def setDashboardGraphDepth(self, depth: int) -> bool:
        """Switch the bounded Home graph between one and two relationship hops."""

        normalized = 2 if int(depth or 1) >= 2 else 1
        if normalized == self._dashboard_graph_depth:
            return True
        self._dashboard_graph_depth = normalized
        self._generation += 1
        self.changed.emit()
        return True

    @Slot(str, str, result=bool)
    def setDashboardPathEndpoint(self, role: str, entity_id: str) -> bool:
        """Set one endpoint for shortest-path highlighting in the Home graph."""

        normalized_role = str(role or "").strip().lower()
        normalized_id = str(entity_id or "").strip()
        if normalized_role not in {"start", "end"}:
            return False
        if normalized_id and not self._dashboard_entity_in_current_case(normalized_id):
            return False
        if normalized_role == "start":
            self._dashboard_path_start_id = normalized_id
        else:
            self._dashboard_path_end_id = normalized_id
        self._generation += 1
        self.changed.emit()
        return True

    @Slot()
    def clearDashboardPath(self) -> None:
        self._dashboard_path_start_id = ""
        self._dashboard_path_end_id = ""
        self._generation += 1
        self.changed.emit()

    @Slot(result=bool)
    def openDashboardFocus(self) -> bool:
        """Open the selected Home object using the normal entity navigation contract."""

        focus_id = str(self._dashboard_focus_entity_id or "").strip()
        return self.openEntity(focus_id) if focus_id else False

    def _dashboard_entity_in_current_case(self, entity_id: str) -> bool:
        normalized = str(entity_id or "").strip()
        if not normalized or not self._current_case_id:
            return False
        service = getattr(self._container, "entity_service", None)
        if service is None:
            graph = self._current_workspace().get("graph", {}) if self._current_workspace() else {}
            return normalized in {str(item.get("id") or "") for item in list(graph.get("nodes") or [])}
        try:
            entity = service.get_entity(UUID(normalized))
        except Exception:
            return False
        return entity is not None and str(getattr(entity, "case_id", "")) == self._current_case_id

    @Slot(str, result=bool)
    def openReport(self, report_id: str) -> bool:
        """Open one persisted report in the QML report reader."""

        normalized = str(report_id or "").strip()
        if not normalized:
            return False

        report = None
        service = getattr(self._container, "report_service", None)
        if service is not None:
            try:
                report_uuid = UUID(normalized)
                getter = getattr(service, "get_report", None)
                if not callable(getter):
                    getter = getattr(service, "get", None)
                if callable(getter):
                    report = getter(report_uuid)
                if report is None:
                    repository = getattr(service, "repository", None)
                    repository_get = getattr(repository, "get", None)
                    if callable(repository_get):
                        report = repository_get(report_uuid)
            except Exception:
                LOGGER.debug("Unable to resolve report through report service", exc_info=True)

        data: dict[str, Any] = {}
        if report is not None:
            data = self._model_dict(report)
        else:
            for row in list(self._page_records.get("reports") or []):
                if str(row.get("id") or "") == normalized:
                    data = dict(row)
                    break

        if not data:
            self._set_message("The selected report is unavailable.")
            return False

        case_id = str(data.get("case_id") or self._current_case_id or "")
        if self._current_case_id and case_id and case_id != self._current_case_id:
            self._set_message("The selected report is outside the current investigation.")
            return False

        report_type = data.get("type") or "report"
        report_type = getattr(report_type, "value", report_type)
        self._current_report_id = normalized
        self._current_report_snapshot = {
            "id": normalized,
            "caseId": case_id,
            "caseTitle": self.currentCaseTitle,
            "title": str(data.get("title") or "Untitled report"),
            "type": str(report_type or "report").replace("_", " ").title(),
            "description": str(data.get("description") or ""),
            "content": str(data.get("content") or ""),
            "createdAt": self._date_text(data.get("created_at")),
            "updatedAt": self._date_text(data.get("updated_at")),
        }
        self._set_message("")
        self._generation += 1
        self.changed.emit()
        self.navigationRequested.emit("report")
        return True

    @Slot()
    def closeReport(self) -> None:
        self.navigationRequested.emit("reports")

    @Slot(result=bool)
    def copyCurrentReport(self) -> bool:
        content = str(self._current_report_snapshot.get("content") or "")
        if not content:
            self._set_message("This report has no content to copy.")
            return False
        QGuiApplication.clipboard().setText(content)
        self._set_message("Report copied to clipboard.")
        return True

    @Slot(str, "QVariant", result=bool)
    def setUiSetting(self, key: str, value: Any) -> bool:
        normalized = str(key or "").strip()
        if normalized not in {
            "showWorldMap", "showSlogan",
            "graphNodeLimit", "graphDepth", "graphEdgeLabels",
        }:
            return False

        if normalized in {"showWorldMap", "showSlogan", "graphEdgeLabels"}:
            stored: Any = bool(value)
        elif normalized == "graphNodeLimit":
            try:
                stored = min(80, max(12, int(value)))
            except (TypeError, ValueError):
                return False
        else:
            try:
                stored = 2 if int(value) >= 2 else 1
            except (TypeError, ValueError):
                return False

        self._desktop_settings.setValue(f"desktop_ui/{normalized}", stored)
        self._desktop_settings.sync()
        self._generation += 1
        self.changed.emit()
        return True

    @Slot()
    def resetUiSettings(self) -> None:
        for key in (
            "showWorldMap", "showSlogan",
            "graphNodeLimit", "graphDepth", "graphEdgeLabels",
        ):
            self._desktop_settings.remove(f"desktop_ui/{key}")
        self._desktop_settings.sync()
        self._generation += 1
        self.changed.emit()

    @Slot(str, result=bool)
    def selectGraphEntity(self, entity_id: str) -> bool:
        normalized = str(entity_id or "").strip()
        if not normalized:
            return False
        payload = self._graph_workspace_payload()
        valid_ids = {str(item.get("id") or "") for item in payload.get("options", [])}
        if normalized not in valid_ids:
            return False
        self._graph_focus_entity_id = normalized
        self._generation += 1
        self.changed.emit()
        return True

    @Slot(int, result=bool)
    def setGraphDepth(self, depth: int) -> bool:
        return self.setUiSetting("graphDepth", 2 if int(depth or 1) >= 2 else 1)

    @Slot(str, result=bool)
    def openGraphEntity(self, entity_id: str) -> bool:
        normalized = str(entity_id or "").strip()
        if not normalized:
            return False
        service = getattr(self._container, "entity_service", None)
        if service is not None:
            try:
                entity = service.get_entity(UUID(normalized))
                entity_type = str(
                    getattr(
                        getattr(entity, "entity_type", None),
                        "value",
                        getattr(entity, "entity_type", ""),
                    )
                    or ""
                ).strip().lower()
                if entity_type == EntityType.PERSON.value:
                    return self.openEntity(normalized)
            except Exception:
                LOGGER.debug("Unable to open Graph entity", exc_info=True)
        return self.selectGraphEntity(normalized)

    @Slot(str, result=bool)
    def setEntityCategory(self, category: str) -> bool:
        """Switch the virtualized Entity Directory to a bounded type group."""

        normalized = str(category or "all").strip().lower()
        if normalized not in self.ENTITY_CATEGORY_TYPES:
            return False
        if normalized == self._entity_category and "entities" in self._page_records:
            return True

        self._entity_category = normalized
        self._page_records.pop("entities", None)
        self._page_offsets.pop("entities", None)
        self._page_totals.pop("entities", None)
        self._page_errors.pop("entities", None)
        self._load_page("entities", 0, notify=False)
        self._generation += 1
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    def openEntity(self, entity_id: str) -> bool:
        """Open a PERSON page, or an explicit URL-backed entity when applicable."""

        normalized = str(entity_id or "").strip()
        if not normalized:
            return False
        service = getattr(self._container, "entity_service", None)
        if service is None:
            # Legacy test/workspace path: only PERSON snapshots can be resolved
            # from already loaded records.
            record = next(
                (item for item in self._page_records.get("entities", []) if item.get("id") == normalized),
                None,
            )
            if record and str(record.get("entityType") or "") == EntityType.PERSON.value:
                self._current_entity_id = normalized
                self._current_entity_snapshot = {
                    "id": normalized,
                    "title": str(record.get("title") or "Person"),
                    "type": EntityType.PERSON.value,
                    "typeLabel": "Person",
                    "confidenceText": str(record.get("meta") or ""),
                    "caseTitle": self.currentCaseTitle,
                    "description": str(record.get("detail") or ""),
                    "normalizedValue": "",
                    "createdAt": "",
                    "updatedAt": "",
                    "metadataRows": [],
                    "links": [],
                    "photos": [],
                    "files": [],
                    "avatarUrl": "",
                    "evidence": [],
                    "relatedEntities": [],
                    "associationNotice": (
                        "Related profiles and pages are shown only when supported by "
                        "shared evidence or explicit source URLs; they are not automatic "
                        "identity claims."
                    ),
                }
                self.navigationRequested.emit("person")
                self._generation += 1
                self.changed.emit()
                return True
            return False

        try:
            entity = service.get_entity(UUID(normalized))
        except Exception as exc:
            LOGGER.exception("Unable to open entity")
            self._set_message(f"Unable to open entity: {exc}")
            return False
        if entity is None:
            self._set_message("The selected entity is unavailable.")
            return False

        entity_type = getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", ""))
        if str(entity_type) != EntityType.PERSON.value:
            explicit_url = self._entity_explicit_url(entity)
            if explicit_url:
                return self.openExternalUrl(explicit_url)
            self._set_message("A dedicated detail page is currently available for person entities.")
            return False

        try:
            snapshot = self._build_person_snapshot(entity)
        except Exception as exc:
            LOGGER.exception("Unable to build person entity snapshot")
            self._set_message(f"Unable to load person details: {exc}")
            return False

        self._current_entity_id = normalized
        self._current_entity_snapshot = snapshot
        self._set_message("")
        self._generation += 1
        self.changed.emit()
        self.navigationRequested.emit("person")
        return True

    @Slot()
    def closeEntity(self) -> None:
        self.navigationRequested.emit("entities")

    @Slot(str, result=bool)
    def openExternalUrl(self, value: str) -> bool:
        """Open only an explicit HTTP(S) URL; never execute arbitrary URI schemes."""

        normalized = self._normalized_external_url(value)
        if not normalized:
            self._set_message("Only explicit http:// or https:// links can be opened.")
            return False
        opened = bool(QDesktopServices.openUrl(QUrl(normalized)))
        if not opened:
            self._set_message("The system browser could not open this link.")
        return opened

    @Slot(str, str, str, str, result="QVariantMap")
    def addPersonAttachment(
        self,
        kind: str,
        title: str,
        value: str,
        description: str,
    ) -> dict[str, Any]:
        """Attach analyst-supplied material to the currently opened PERSON."""

        entity_id = str(self._current_entity_id or "").strip()
        if not entity_id:
            return {"ok": False, "error": "Open a person card before adding an attachment."}

        entity_service = getattr(self._container, "entity_service", None)
        source_service = getattr(self._container, "source_service", None)
        evidence_service = getattr(self._container, "evidence_service", None)
        link_service = getattr(self._container, "evidence_link_service", None)
        if any(service is None for service in (
            entity_service,
            source_service,
            evidence_service,
            link_service,
        )):
            return {"ok": False, "error": "Person attachment services are unavailable."}

        try:
            person = entity_service.get_entity(UUID(entity_id))
        except Exception as exc:
            LOGGER.exception("Unable to resolve person for manual attachment")
            return {"ok": False, "error": f"Unable to resolve person: {exc}"}

        if person is None:
            return {"ok": False, "error": "The selected person no longer exists."}

        normalized_value = str(value or "").strip()
        if str(kind or "").strip().lower() in {"photo", "file"}:
            url = QUrl(normalized_value)
            if url.isLocalFile():
                normalized_value = url.toLocalFile()

        service = PersonAttachmentService(
            source_service=source_service,
            evidence_service=evidence_service,
            entity_service=entity_service,
            evidence_link_service=link_service,
        )
        result = None
        try:
            result = service.add(
                person=person,
                kind=str(kind or ""),
                title=str(title or ""),
                value=normalized_value,
                description=str(description or ""),
            )
            if result.duplicate:
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "This item is already attached to the person.",
                }
            self._container.commit()
        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug("Rollback after person attachment failure failed", exc_info=True)
            if result is not None and result.managed_path:
                service.cleanup_managed_file(result.managed_path)
            LOGGER.exception("Unable to add person attachment")
            return {"ok": False, "error": str(exc)}

        try:
            refreshed = entity_service.get_entity(UUID(entity_id)) or person
            self._current_entity_snapshot = self._build_person_snapshot(refreshed)
        except Exception:
            LOGGER.exception("Attachment saved but person snapshot refresh failed")

        self._avatar_cache.pop(entity_id, None)
        for key in ("entities", "evidence"):
            self._page_records.pop(key, None)
            self._page_offsets.pop(key, None)
            self._page_totals.pop(key, None)
            self._page_errors.pop(key, None)
        self._refresh_entity_type_counts()
        self._generation += 1
        self.changed.emit()
        self._set_message("Person attachment saved.")
        return {
            "ok": True,
            "duplicate": False,
            "message": "Person attachment saved.",
            "evidenceId": result.evidence_id if result is not None else "",
            "relatedEntityId": result.related_entity_id if result is not None else "",
        }

    @Slot(str, str, str, result="QVariantMap")
    def reviewIdentityCandidate(
        self,
        entity_id: str,
        decision: str,
        note: str = "",
    ) -> dict[str, Any]:
        """Persist a human identity decision for an account/profile candidate."""

        person_id = str(
            self._current_entity_id
            or ""
        ).strip()
        candidate_id = str(
            entity_id
            or ""
        ).strip()

        if not person_id:
            return {
                "ok": False,
                "error": "Open a person card first.",
            }

        if not candidate_id:
            return {
                "ok": False,
                "error": "Select an identity candidate first.",
            }

        entity_service = getattr(
            self._container,
            "entity_service",
            None,
        )
        source_service = getattr(
            self._container,
            "source_service",
            None,
        )
        evidence_service = getattr(
            self._container,
            "evidence_service",
            None,
        )
        link_service = getattr(
            self._container,
            "evidence_link_service",
            None,
        )

        if any(
            service is None
            for service in (
                entity_service,
                source_service,
                evidence_service,
                link_service,
            )
        ):
            return {
                "ok": False,
                "error": "Identity review services are unavailable.",
            }

        try:
            person = entity_service.get_entity(
                UUID(person_id)
            )
            candidate = entity_service.get_entity(
                UUID(candidate_id)
            )

            review_service = (
                PersonIdentityReviewService(
                    source_service=source_service,
                    evidence_service=evidence_service,
                    evidence_link_service=link_service,
                )
            )

            result = review_service.record(
                person=person,
                candidate=candidate,
                decision=decision,
                note=note,
            )

            profile_result = None

            if (
                result.decision
                ==
                IdentityReviewDecision
                .CONFIRMED
                .value
            ):
                profile_result = (
                    PersonProfileSelectionService(
                        source_service=source_service,
                        evidence_service=evidence_service,
                        evidence_link_service=link_service,
                    )
                    .add(
                        person=person,
                        candidate=candidate,
                    )
                )

            self._container.commit()

        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug(
                    "Rollback after identity review failed",
                    exc_info=True,
                )

            LOGGER.exception(
                "Unable to persist identity review decision"
            )

            return {
                "ok": False,
                "error": str(exc),
            }

        try:
            refreshed = (
                entity_service.get_entity(
                    UUID(person_id)
                )
                or person
            )
            self._current_entity_snapshot = (
                self._build_person_snapshot(
                    refreshed
                )
            )
        except Exception:
            LOGGER.exception(
                "Identity decision saved but PERSON snapshot refresh failed"
            )

        for key in (
            "entities",
            "evidence",
        ):
            self._page_records.pop(
                key,
                None,
            )
            self._page_offsets.pop(
                key,
                None,
            )
            self._page_totals.pop(
                key,
                None,
            )
            self._page_errors.pop(
                key,
                None,
            )

        self._refresh_entity_type_counts()
        self._generation += 1
        self.changed.emit()

        message = {
            "confirmed": "Account confirmed and added to the person profile.",
            "review": "Account marked for further review.",
            "rejected": "Account rejected for this person.",
        }.get(
            result.decision,
            "Identity review saved.",
        )

        self._set_message(
            message
        )

        return {
            "ok": True,
            "decision": result.decision,
            "previousDecision": result.previous_decision,
            "duplicate": result.duplicate,
            "evidenceId": result.evidence_id,
            "selectedEntityId": result.candidate_entity_id,
            "profileBound": bool(
                result.decision == "confirmed"
            ),
            "profileSelectionDuplicate": bool(
                getattr(
                    profile_result,
                    "duplicate",
                    False,
                )
                if profile_result is not None
                else False
            ),
            "message": message,
        }

    @Slot(str, result="QVariantMap")
    def identityReviewHistory(
        self,
        entity_id: str,
    ) -> dict[str, Any]:
        """Return append-only analyst review history for one candidate."""

        person_id = str(
            self._current_entity_id
            or ""
        ).strip()
        candidate_id = str(
            entity_id
            or ""
        ).strip()

        if not person_id:
            return {
                "ok": False,
                "error": "Open a person card first.",
                "items": [],
            }

        if not candidate_id:
            return {
                "ok": False,
                "error": "Select an identity candidate first.",
                "items": [],
            }

        source_service = getattr(
            self._container,
            "source_service",
            None,
        )
        evidence_service = getattr(
            self._container,
            "evidence_service",
            None,
        )
        link_service = getattr(
            self._container,
            "evidence_link_service",
            None,
        )

        if any(
            service is None
            for service in (
                source_service,
                evidence_service,
                link_service,
            )
        ):
            return {
                "ok": False,
                "error": "Identity review services are unavailable.",
                "items": [],
            }

        try:
            service = PersonIdentityReviewService(
                source_service=source_service,
                evidence_service=evidence_service,
                evidence_link_service=link_service,
            )

            items = service.decision_history(
                UUID(person_id),
                UUID(candidate_id),
            )
        except Exception as exc:
            LOGGER.exception(
                "Unable to load identity review history"
            )
            return {
                "ok": False,
                "error": str(exc),
                "items": [],
            }

        return {
            "ok": True,
            "items": items,
            "count": len(items),
        }

    @Slot(str, result="QVariantMap")
    def addExistingDataToPerson(self, entity_id: str) -> dict[str, Any]:
        """Attach already-persisted investigation data to the open PERSON card.

        The action records a new analyst-selection Evidence item and links it to
        both the PERSON and the selected entity.  It never changes the original
        OSINT finding and never marks identity as verified.
        """

        person_id = str(self._current_entity_id or "").strip()
        candidate_id = str(entity_id or "").strip()
        if not person_id:
            return {"ok": False, "error": "Open a person card first."}
        if not candidate_id:
            return {"ok": False, "error": "Select an investigation item first."}

        entity_service = getattr(self._container, "entity_service", None)
        source_service = getattr(self._container, "source_service", None)
        evidence_service = getattr(self._container, "evidence_service", None)
        link_service = getattr(self._container, "evidence_link_service", None)
        if any(service is None for service in (entity_service, source_service, evidence_service, link_service)):
            return {"ok": False, "error": "Profile selection services are unavailable."}

        try:
            person = entity_service.get_entity(UUID(person_id))
            candidate = entity_service.get_entity(UUID(candidate_id))
        except Exception as exc:
            LOGGER.exception("Unable to resolve profile selection entities")
            return {"ok": False, "error": f"Unable to resolve selected data: {exc}"}

        service = PersonProfileSelectionService(
            source_service=source_service,
            evidence_service=evidence_service,
            evidence_link_service=link_service,
        )
        try:
            result = service.add(person=person, candidate=candidate)
            if result.duplicate:
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "This item is already part of the person profile.",
                }
            self._container.commit()
        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug("Rollback after profile selection failed", exc_info=True)
            LOGGER.exception("Unable to attach existing intelligence to person")
            return {"ok": False, "error": str(exc)}

        try:
            refreshed = entity_service.get_entity(UUID(person_id)) or person
            self._current_entity_snapshot = self._build_person_snapshot(refreshed)
        except Exception:
            LOGGER.exception("Profile selection saved but PERSON snapshot refresh failed")

        self._page_records.pop("evidence", None)
        self._page_offsets.pop("evidence", None)
        self._page_totals.pop("evidence", None)
        self._page_errors.pop("evidence", None)
        self._generation += 1
        self.changed.emit()
        self._set_message("Existing intelligence added to person profile.")
        return {
            "ok": True,
            "duplicate": False,
            "message": "Existing intelligence added to person profile.",
            "evidenceId": result.evidence_id,
            "selectedEntityId": result.selected_entity_id,
        }

    @Slot(str, result=bool)
    def openManagedAttachment(self, value: str) -> bool:
        """Open only a file stored inside the managed person-attachment directory."""

        path = PersonAttachmentService.managed_file_path(value)
        if path is None or not path.is_file():
            self._set_message("The managed attachment file is unavailable.")
            return False
        opened = bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
        if not opened:
            self._set_message("The system could not open this attachment.")
        return opened

    @Slot(str, str, result=bool)
    def registrySearch(self, mode: str, value: str) -> bool:
        normalized_value = str(value or "").strip()
        if not normalized_value:
            self._set_message("Registry search requires a value.")
            return False
        return self._start_registry_operation(
            mode=str(mode or "").strip(),
            value=normalized_value,
            persist=False,
        )

    @Slot(result=bool)
    def registryPersistLast(self) -> bool:
        if not self._current_case_id:
            self._set_message(
                "Select an investigation before saving registry intelligence."
            )
            return False

        current = dict(self._registry_run)
        if not current or not current.get("hasRun"):
            self._set_message("Run a registry search before saving results.")
            return False
        if str(current.get("status") or "") not in {
            "completed",
            "completed_with_errors",
        }:
            self._set_message("Wait for the registry search to finish.")
            return False

        summary = dict(current.get("summary") or {})
        if int(summary.get("persistable") or 0) < 1:
            self._set_message(
                "The current registry results are candidates only and cannot "
                "be saved as verified evidence."
            )
            return False

        mode = str(current.get("mode") or "").strip()
        value = str(current.get("value") or "").strip()
        if not mode or not value:
            self._set_message("The last registry query is unavailable.")
            return False

        return self._start_registry_operation(
            mode=mode,
            value=value,
            persist=True,
        )

    def _start_registry_operation(
        self,
        *,
        mode: str,
        value: str,
        persist: bool,
    ) -> bool:
        if self._registry_busy:
            self._set_message("A Registry Intelligence operation is already running.")
            return False

        case_id = self._current_case_id if persist else ""
        case_title = self.currentCaseTitle if persist else ""
        previous_run = dict(self._registry_run)
        started_at = datetime.now()

        if persist:
            running = dict(previous_run)
            running.update({
                "hasRun": True,
                "status": "saving",
                "operation": "save",
                "caseId": case_id,
                "caseTitle": case_title,
                "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
                "error": "",
            })
        else:
            running = {
                "hasRun": True,
                "status": "running",
                "operation": "search",
                "mode": mode,
                "value": value,
                "records": [],
                "providers": [],
                "route": {},
                "summary": {
                    "records": 0,
                    "persistable": 0,
                    "candidates": 0,
                    "sensitiveLegal": 0,
                    "providerErrors": 0,
                },
                "persistence": {
                    "attempted": False,
                    "sourcesCreated": 0,
                    "evidencesCreated": 0,
                    "entitiesCreated": 0,
                    "linksCreated": 0,
                    "skippedRecords": 0,
                    "errors": [],
                    "records": [],
                },
                "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
                "durationSeconds": 0.0,
                "durationText": "Running…",
                "error": "",
            }

        self._registry_context = {
            "operation": "save" if persist else "search",
            "mode": mode,
            "value": value,
            "caseId": case_id,
            "caseTitle": case_title,
            "startedAt": started_at,
            "previousRun": previous_run,
        }
        self._registry_run = running
        self._registry_busy = True
        self._set_message(
            (
                f"Saving registry intelligence to {case_title}."
                if persist
                else f"Registry search running for {value}."
            )
        )
        self._generation += 1
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = RegistrySearchWorker(
                mode=mode,
                value=value,
                persist=persist,
                case_id=case_id or None,
            )
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_registry_worker_succeeded)
            worker.failed.connect(self._on_registry_worker_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_registry_thread_finished)
            thread.finished.connect(thread.deleteLater)

            self._registry_thread = thread
            self._registry_worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start Registry Intelligence worker")
            self._registry_busy = False
            self._registry_thread = None
            self._registry_worker = None
            self._registry_context = {}
            if persist and previous_run:
                failed = dict(previous_run)
                failed.update({
                    "status": "failed",
                    "operation": "save",
                    "error": str(exc),
                })
                self._registry_run = failed
            else:
                self._registry_run = {
                    "hasRun": True,
                    "status": "failed",
                    "operation": "search",
                    "mode": mode,
                    "value": value,
                    "records": [],
                    "providers": [],
                    "summary": {},
                    "error": str(exc),
                }
            self._set_message(f"Unable to start registry operation: {exc}")
            self._generation += 1
            self.changed.emit()
            return False

    @Slot(object)
    def _on_registry_worker_succeeded(self, result: object) -> None:
        context = dict(self._registry_context)
        if not context:
            return

        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            snapshot = {}
        duration = self._safe_float(payload.get("duration"))

        run = dict(snapshot)
        summary = dict(run.get("summary") or {})
        persistence = dict(run.get("persistence") or {})
        provider_errors = int(summary.get("providerErrors") or 0)
        persistence_errors = len(list(persistence.get("errors") or []))
        run["status"] = (
            "completed_with_errors"
            if provider_errors or persistence_errors
            else "completed"
        )
        run["durationSeconds"] = round(duration, 3)
        run["durationText"] = f"{duration:.2f}s"
        run["startedLabel"] = context["startedAt"].strftime(
            "%b %d, %Y · %H:%M:%S"
        )
        run["caseId"] = str(context.get("caseId") or "")
        run["caseTitle"] = str(context.get("caseTitle") or "")
        run["error"] = ""
        self._registry_run = run

        operation = str(context.get("operation") or "search")
        if operation == "save":
            self._invalidate_after_registry(
                case_id=str(context.get("caseId") or "")
            )
            case_title = str(context.get("caseTitle") or "investigation")
            self._set_message(
                "Registry intelligence saved to "
                f"{case_title}: "
                f"{int(persistence.get('evidencesCreated') or 0)} evidence, "
                f"{int(persistence.get('entitiesCreated') or 0)} entities, "
                f"{int(persistence.get('linksCreated') or 0)} links created; "
                f"{int(persistence.get('skippedRecords') or 0)} skipped."
            )
        else:
            records = int(summary.get("records") or 0)
            candidates = int(summary.get("candidates") or 0)
            suffix = (
                f" {candidates} name-only candidate(s) are not verified evidence."
                if candidates
                else ""
            )
            self._set_message(
                f"Registry search completed with {records} record(s)." + suffix
            )

        self._generation += 1
        self.changed.emit()

    @Slot(object)
    def _on_registry_worker_failed(self, result: object) -> None:
        context = dict(self._registry_context)
        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Unknown registry error")
        operation = str(context.get("operation") or payload.get("operation") or "search")

        if operation == "save" and context.get("previousRun"):
            run = dict(context["previousRun"])
            run.update({
                "status": "failed",
                "operation": "save",
                "error": error,
            })
            self._registry_run = run
        else:
            self._registry_run = {
                "hasRun": True,
                "status": "failed",
                "operation": "search",
                "mode": str(context.get("mode") or payload.get("mode") or ""),
                "value": str(context.get("value") or payload.get("value") or ""),
                "records": [],
                "providers": [],
                "summary": {
                    "records": 0,
                    "persistable": 0,
                    "candidates": 0,
                    "sensitiveLegal": 0,
                    "providerErrors": 1,
                },
                "error": error,
            }

        self._set_message(f"Registry Intelligence {operation} failed: {error}")
        self._generation += 1
        self.changed.emit()

    @Slot()
    def _on_registry_thread_finished(self) -> None:
        self._registry_busy = False
        self._registry_worker = None
        self._registry_thread = None
        self._registry_context = {}
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
        page_key = (page or "").strip().lower()
        if page_key == "cases":
            self.openCase(record_id)
        elif page_key == "entities":
            self.openEntity(record_id)
        elif page_key == "reports":
            self.openReport(record_id)

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
            graph = self._graph_workspace_payload()
            return [
                {
                    "id": str(node.get("id") or ""),
                    "title": str(node.get("label") or "Unnamed entity"),
                    "detail": str(node.get("type") or "entity").replace("_", " ").title(),
                    "status": "Connected" if int(node.get("degree") or 0) > 0 else "Isolated",
                    "meta": f"{int(node.get('degree') or 0)} links",
                    "color": "#68a4ff",
                    "tint": "#142b47",
                }
                for node in list(graph.get("allNodes") or graph.get("nodes") or [])
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
            return self._metric_set(
                self._page_totals.get("entities", len(records)),
                "People",
                scope,
                "PERSON",
                "Directory type",
                "Only people are shown here",
                len(records),
                "Loaded",
                "Technical entities remain in Evidence and Graph",
            )
        if page == "evidence":
            hashed = sum(1 for item in records if item.get("meta"))
            return self._metric_set(self._page_totals.get("evidence", len(records)), "Evidence items", scope, hashed, "Hashed", "SHA-256 recorded", 0, "Needs review", "No persisted review status")
        if page == "reports":
            return self._metric_set(self._page_totals.get("reports", len(records)), "Reports", scope, 0, "Report types", "Current scope", 0, "In review", "No workflow status model")
        if page == "timeline":
            return self._metric_set(self._page_totals.get("timeline", len(records)), "Events", scope, 0, "Event types", "Current scope", 0, "Anomalies", "No persisted anomaly metric")
        if page == "graph":
            graph_stats = self._graph_workspace_payload().get("statistics", {})
            return self._metric_set(int(graph_stats.get("nodeCount") or len(records)), "Nodes", scope, int(graph_stats.get("edgeCount") or 0), "Relationships", "Current case", int(graph_stats.get("isolatedNodes") or 0), "Isolated", "No relationships")
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
        if page == "entities":
            items.append({
                "title": "People only",
                "detail": (
                    "Email, phone, username, URL, domain and other technical "
                    "entities stay internal and appear through Person cards, "
                    "Evidence and Graph."
                ),
                "color": "#a98be9",
            })
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
            entity_type = str(item.get("type") or item.get("entity_type") or "other").strip().lower()
            detail = entity_type.replace("_", " ").title()
            meta = f"{float(confidence) * 100:.0f}%" if confidence is not None else ""
            title = item.get("value")
            status = detail
            metadata = self._metadata_dict(item.get("metadata_json") or item.get("metadata"))
            explicit_url = self._explicit_url_from_entity_values(
                entity_type=entity_type,
                value=str(item.get("value") or ""),
                metadata=metadata,
            )
            color, tint = self._entity_colors(entity_type)
            interactive = entity_type == EntityType.PERSON.value or bool(explicit_url)
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
        result = {
            "id": str(item.get("id") or ""),
            "title": str(title or "Untitled record"),
            "detail": str(detail),
            "status": str(status),
            "meta": str(meta),
            "color": "#68a4ff",
            "tint": "#142b47",
        }
        if kind == "entities":
            result.update({
                "entityType": entity_type,
                "url": explicit_url,
                "interactive": interactive,
                "avatarUrl": (
                    self._person_avatar_url(item.get("id"))
                    if entity_type == EntityType.PERSON.value
                    else ""
                ),
                "color": color,
                "tint": tint,
            })
        elif kind == "reports":
            result.update({
                "case_id": str(item.get("case_id") or ""),
                "type": str(item.get("type") or "report"),
                "content": str(item.get("content") or ""),
                "description": str(item.get("description") or ""),
                "created_at": item.get("created_at") or "",
                "updated_at": item.get("updated_at") or "",
                "interactive": True,
            })
        return result

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
        """Map the worker's recursive transport snapshot into QML rows."""
        findings: list[dict[str, Any]] = []
        leads: list[dict[str, Any]] = []
        connectors: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        entities_by_id: dict[str, dict[str, Any]] = {}
        evidence_by_id: dict[str, dict[str, Any]] = {}

        raw_runs = snapshot.get("runs")
        recursive = isinstance(raw_runs, list)
        if recursive:
            runs = list(raw_runs or [])
        else:
            # Compatibility with the previous single-target worker snapshot.
            runs = [{
                "targetType": target_type.value,
                "targetValue": value,
                "depth": 0,
                "executions": list(snapshot.get("executions") or []),
                "persistences": list(snapshot.get("persistences") or []),
            }]

        for run_index, run in enumerate(runs):
            if not isinstance(run, dict):
                continue

            run_target_type = str(run.get("targetType") or target_type.value)
            run_target_value = str(run.get("targetValue") or value)
            run_depth = self._safe_int(run.get("depth"))

            executions = list(run.get("executions") or [])
            for execution_index, execution in enumerate(executions):
                if not isinstance(execution, dict):
                    continue
                goal = str(execution.get("goal") or "")
                execution_status = str(execution.get("status") or "unknown")
                execution_error = str(execution.get("error") or "").strip()
                records = list(execution.get("records") or [])

                if execution_error and not records:
                    errors.append({
                        "id": f"execution:{run_index}:{execution_index}",
                        "title": (
                            goal.replace("_", " ").title()
                            or "OSINT execution"
                        ),
                        "detail": execution_error,
                        "status": execution_status.replace("_", " ").title(),
                        "meta": f"Depth {run_depth} · {run_target_value}",
                        "targetType": run_target_type,
                        "targetValue": run_target_value,
                        "depth": run_depth,
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
                                f"{run_index}:{execution_index}:"
                                f"{record_index}:{finding_index}"
                            ),
                            is_lead=is_lead,
                        )
                        row["targetType"] = run_target_type
                        row["targetValue"] = run_target_value
                        row["depth"] = run_depth
                        if is_lead:
                            lead_count += 1
                            leads.append(row)
                        else:
                            finding_count += 1
                            findings.append(row)

                    result_error = str(record.get("error") or "").strip()
                    execution_time = self._safe_float(
                        record.get("executionTime")
                    )
                    connector_color, connector_tint = (
                        self._osint_status_colors(status)
                    )
                    connectors.append({
                        "id": (
                            f"{run_index}:{execution_index}:"
                            f"{record_index}:{connector_name}"
                        ),
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
                        "targetType": run_target_type,
                        "targetValue": run_target_value,
                        "depth": run_depth,
                        "color": connector_color,
                        "tint": connector_tint,
                    })

                    if result_error:
                        errors.append({
                            "id": (
                                f"connector:{run_index}:"
                                f"{execution_index}:{record_index}"
                            ),
                            "title": connector_name,
                            "detail": result_error,
                            "status": status.replace("_", " ").title(),
                            "meta": f"Depth {run_depth} · {run_target_value}",
                            "targetType": run_target_type,
                            "targetValue": run_target_value,
                            "depth": run_depth,
                            "color": "#f25d68",
                            "tint": "#3a1e26",
                        })

            for persistence in list(run.get("persistences") or []):
                if not isinstance(persistence, dict):
                    continue
                for persisted in list(persistence.get("persisted") or []):
                    if not isinstance(persisted, dict):
                        continue
                    evidence = persisted.get("evidence")
                    if isinstance(evidence, dict):
                        evidence_id = str(evidence.get("id") or "")
                        if evidence_id and evidence_id not in evidence_by_id:
                            evidence_type_text = str(
                                evidence.get("type") or "evidence"
                            )
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
                                "status": (
                                    evidence_type_text
                                    .replace("_", " ")
                                    .title()
                                ),
                                "meta": (
                                    f"Depth {run_depth} · {run_target_value}"
                                ),
                                "targetType": run_target_type,
                                "targetValue": run_target_value,
                                "depth": run_depth,
                                "color": "#68a4ff",
                                "tint": "#142b47",
                            }

                    for entity in list(persisted.get("entities") or []):
                        if not isinstance(entity, dict):
                            continue
                        entity_id = str(entity.get("id") or "")
                        if not entity_id or entity_id in entities_by_id:
                            continue
                        entity_type_text = str(
                            entity.get("type") or "entity"
                        )
                        confidence = self._safe_optional_float(
                            entity.get("confidence")
                        )
                        entities_by_id[entity_id] = {
                            "id": entity_id,
                            "title": str(
                                entity.get("value") or "Unnamed entity"
                            ),
                            "detail": (
                                entity_type_text.replace("_", " ").title()
                            ),
                            "status": "Entity",
                            "meta": (
                                self._confidence_text(confidence)
                                + f" · D{run_depth}"
                            ),
                            "confidence": confidence,
                            "targetType": run_target_type,
                            "targetValue": run_target_value,
                            "depth": run_depth,
                            "color": "#a98be9",
                            "tint": "#271f43",
                        }

        status_counts = Counter(
            str(item.get("status") or "unknown") for item in connectors
        )
        success_like = (
            status_counts.get("success", 0)
            + status_counts.get("partial", 0)
        )
        if success_like:
            run_status = "completed_with_errors" if errors else "completed"
        elif connectors or errors:
            run_status = "failed"
        else:
            run_status = "completed"

        counts = snapshot.get("counts")
        if not isinstance(counts, dict):
            counts = {}

        recursion = snapshot.get("recursion")
        if not isinstance(recursion, dict):
            recursion = {}

        targets_processed = int(
            recursion.get("targetsProcessed")
            or (len(runs) if recursive else 1)
        )
        candidates_discovered = int(
            recursion.get("candidatesDiscovered") or 0
        )
        candidates_enqueued = int(
            recursion.get("candidatesEnqueued") or 0
        )
        candidates_deduplicated = int(
            recursion.get("candidatesDeduplicated") or 0
        )
        new_entities_count = int(
            recursion.get("newEntitiesCount")
            or counts.get("entitiesCreated")
            or 0
        )
        stop_reason = str(recursion.get("stopReason") or "")

        completed_at = datetime.now()
        return {
            "hasRun": True,
            "status": run_status,
            "recursive": recursive,
            "targetType": target_type.value,
            "targetValue": value,
            "caseId": case_id,
            "caseTitle": case_title,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "completedAt": completed_at.isoformat(timespec="seconds"),
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
            "stopReason": stop_reason,
            "progress": {
                "phase": "completed",
                "targetType": "",
                "targetValue": "",
                "depth": None,
                "targetsProcessed": targets_processed,
                "queuedTargets": 0,
                "candidatesDiscovered": candidates_discovered,
                "candidatesEnqueued": candidates_enqueued,
                "newEntitiesCount": new_entities_count,
                "elapsedSeconds": round(duration, 3),
                "stopReason": stop_reason,
            },
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
                "persistedFindings": int(
                    counts.get("persistedFindings") or 0
                ),
                "sourcesCreated": int(counts.get("sourcesCreated") or 0),
                "evidenceCreated": int(counts.get("evidenceCreated") or 0),
                "entitiesCreated": int(counts.get("entitiesCreated") or 0),
                "linksCreated": int(counts.get("linksCreated") or 0),
                "targetsProcessed": targets_processed,
                "queuedTargets": 0,
                "candidatesDiscovered": candidates_discovered,
                "candidatesEnqueued": candidates_enqueued,
                "candidatesDeduplicated": candidates_deduplicated,
                "newEntitiesCount": new_entities_count,
                "maxTargets": int(recursion.get("maxTargets") or 0),
                "timeBudgetSeconds": self._safe_float(
                    recursion.get("timeBudgetSeconds")
                ),
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
            "recursive": True,
            "stopReason": "",
            "progress": {
                "phase": "queued",
                "targetType": target_type.value,
                "targetValue": value,
                "depth": 0,
                "targetsProcessed": 0,
                "queuedTargets": 1,
                "candidatesDiscovered": 0,
                "candidatesEnqueued": 0,
                "newEntitiesCount": 0,
                "elapsedSeconds": 0.0,
                "stopReason": "",
            },
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
                "targetsProcessed": 0,
                "queuedTargets": 1,
                "candidatesDiscovered": 0,
                "candidatesEnqueued": 0,
                "candidatesDeduplicated": 0,
                "newEntitiesCount": 0,
                "maxTargets": 24,
                "timeBudgetSeconds": 180.0,
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

    def _invalidate_after_registry(self, *, case_id: str) -> None:
        session = getattr(self._container, "session", None)
        if session is not None:
            try:
                session.expire_all()
            except Exception:
                LOGGER.debug(
                    "Unable to expire GUI session after registry persistence",
                    exc_info=True,
                )

        self._workspaces.pop(case_id, None)
        for page in ("entities", "evidence"):
            self._page_records.pop(page, None)
            self._page_offsets.pop(page, None)
            self._page_errors.pop(page, None)
            self._page_totals.pop(page, None)

        parsed_case_id = UUID(case_id) if case_id else None
        for page, attr in (
            ("entities", "entity_service"),
            ("evidence", "evidence_service"),
        ):
            service = getattr(self._container, attr, None)
            if service is None:
                continue
            try:
                if page == "entities":
                    self._page_totals[page] = int(
                        service.count_all(
                            case_id=parsed_case_id,
                            entity_types=self._entity_types_for_category(self._entity_category),
                        )
                    )
                else:
                    self._page_totals[page] = int(
                        service.count_all(case_id=parsed_case_id)
                    )
            except Exception:
                LOGGER.debug(
                    "Unable to refresh %s count after registry persistence",
                    page,
                    exc_info=True,
                )
        self._refresh_entity_type_counts()

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
                if page == "entities":
                    self._page_totals[page] = int(
                        service.count_all(
                            case_id=case_id,
                            entity_types=self._entity_types_for_category(self._entity_category),
                        )
                    )
                else:
                    self._page_totals[page] = int(
                        service.count_all(case_id=case_id)
                    )
            except Exception:
                LOGGER.debug(
                    "Unable to refresh %s count after OSINT",
                    page,
                    exc_info=True,
                )
        self._refresh_entity_type_counts()

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
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

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

    @classmethod
    def _entity_types_for_category(cls, category: str) -> tuple[EntityType, ...]:
        return cls.ENTITY_CATEGORY_TYPES.get(str(category or "all").strip().lower(), ())

    def _refresh_entity_type_counts(self) -> None:
        service = getattr(self._container, "entity_service", None)
        if service is not None and hasattr(service, "count_by_type"):
            try:
                case_id = UUID(self._current_case_id) if self._current_case_id else None
                raw = service.count_by_type(case_id=case_id)
                self._entity_type_counts = {
                    str(getattr(entity_type, "value", entity_type)).strip().lower(): int(count or 0)
                    for entity_type, count in dict(raw or {}).items()
                }
                return
            except Exception:
                LOGGER.debug("Unable to count entities by type", exc_info=True)

        items = self._selected_or_all("entities")
        counts = Counter(
            str(item.get("type") or item.get("entity_type") or "other").strip().lower()
            for item in items
            if isinstance(item, dict)
        )
        self._entity_type_counts = {key: int(value) for key, value in counts.items()}

    def _entity_category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        assigned: set[str] = set()
        for category, entity_types in self.ENTITY_CATEGORY_TYPES.items():
            if category in {"all", "other"}:
                continue
            values = {item.value for item in entity_types}
            assigned.update(values)
            counts[category] = sum(self._entity_type_counts.get(value, 0) for value in values)

        explicit_other = {item.value for item in self.ENTITY_CATEGORY_TYPES["other"]}
        counts["other"] = sum(
            count
            for entity_type, count in self._entity_type_counts.items()
            if entity_type in explicit_other or entity_type not in assigned
        )
        counts["all"] = sum(self._entity_type_counts.values())
        return counts

    @classmethod
    def _identity_resolution_from_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> IdentityResolution | None:
        """Read persisted/search identity fields when provenance carries them."""

        if not isinstance(metadata, dict):
            return None

        status = str(
            metadata.get("identityStatus")
            or metadata.get("identity_status")
            or ""
        ).strip().lower()

        score = cls._safe_optional_float(
            metadata.get("identityAlignmentScore")
            if metadata.get("identityAlignmentScore") is not None
            else metadata.get("identity_alignment_score")
        )

        matched = metadata.get(
            "identityMatchedSignals"
        )
        if matched is None:
            matched = metadata.get(
                "identity_matched_signals"
            )

        conflicts = metadata.get(
            "identityConflictSignals"
        )
        if conflicts is None:
            conflicts = metadata.get(
                "identity_conflict_signals"
            )

        matched_categories = metadata.get(
            "identityMatchedCategories"
        )
        if matched_categories is None:
            matched_categories = metadata.get(
                "identity_matched_categories"
            )

        conflict_categories = metadata.get(
            "identityConflictCategories"
        )
        if conflict_categories is None:
            conflict_categories = metadata.get(
                "identity_conflict_categories"
            )

        pivot_raw = metadata.get(
            "identityPivotAllowed"
        )
        if pivot_raw is None:
            pivot_raw = metadata.get(
                "identity_pivot_allowed"
            )

        if (
            not status
            and score is None
            and not matched
            and not conflicts
        ):
            return None

        def string_tuple(value: Any) -> tuple[str, ...]:
            if not isinstance(
                value,
                (list, tuple, set, frozenset),
            ):
                return ()
            return tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in value
                    if str(item).strip()
                )
            )

        return IdentityResolution(
            status=status or "not_applicable",
            score=max(
                0.0,
                min(
                    100.0,
                    float(score or 0.0),
                ),
            ),
            matched=string_tuple(matched),
            conflicts=string_tuple(conflicts),
            matched_categories=string_tuple(
                matched_categories
            ),
            conflict_categories=string_tuple(
                conflict_categories
            ),
            pivot_allowed=(
                pivot_raw
                if isinstance(
                    pivot_raw,
                    bool,
                )
                else str(
                    pivot_raw
                    or ""
                )
                .strip()
                .lower()
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }
            ),
        )

    @staticmethod
    def _metadata_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _normalized_external_url(value: Any) -> str:
        text = str(value or "").strip()
        if not text or len(text) > 4096:
            return ""
        try:
            parsed = urlparse(text)
        except ValueError:
            return ""
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return ""
        return text

    @classmethod
    def _metadata_explicit_urls(cls, metadata: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        keys = {"finding_url", "profile_url", "public_url", "source_url", "url"}

        def visit(value: Any, depth: int = 0) -> None:
            if depth > 3:
                return
            if isinstance(value, dict):
                for key, nested in value.items():
                    if str(key).strip().lower() in keys:
                        candidate = cls._normalized_external_url(nested)
                        if candidate and candidate not in seen:
                            seen.add(candidate)
                            urls.append(candidate)
                    elif isinstance(nested, (dict, list, tuple)):
                        visit(nested, depth + 1)
            elif isinstance(value, (list, tuple)):
                for nested in value[:50]:
                    visit(nested, depth + 1)

        visit(metadata)
        return urls

    @classmethod
    def _explicit_url_from_entity_values(
        cls,
        *,
        entity_type: str,
        value: str,
        metadata: dict[str, Any],
    ) -> str:
        if entity_type == EntityType.URL.value:
            direct = cls._normalized_external_url(value)
            if direct:
                return direct
        urls = cls._metadata_explicit_urls(metadata)
        return urls[0] if urls else ""

    @classmethod
    def _entity_explicit_url(cls, entity: Any) -> str:
        entity_type = str(
            getattr(getattr(entity, "entity_type", None), "value", getattr(entity, "entity_type", ""))
        ).strip().lower()
        return cls._explicit_url_from_entity_values(
            entity_type=entity_type,
            value=str(getattr(entity, "value", "") or ""),
            metadata=cls._metadata_dict(getattr(entity, "metadata_json", None)),
        )

    @staticmethod
    def _entity_colors(entity_type: str) -> tuple[str, str]:
        key = str(entity_type or "").strip().lower()
        if key == EntityType.PERSON.value:
            return "#a98be9", "#2a2140"
        if key == EntityType.ORGANIZATION.value:
            return "#49c5d8", "#12333a"
        if key in {EntityType.URL.value, EntityType.DOMAIN.value, EntityType.USERNAME.value, EntityType.ACCOUNT.value}:
            return "#68a4ff", "#142b47"
        if key in {EntityType.EMAIL.value, EntityType.PHONE.value}:
            return "#36cfa1", "#12362f"
        if key in {EntityType.LOCATION.value, EntityType.ADDRESS.value}:
            return "#c78cf4", "#30203d"
        if key == EntityType.IP.value:
            return "#e5a84b", "#3b3015"
        return "#8094a8", "#1a2b37"

    PROFILE_CANDIDATE_TYPES: tuple[EntityType, ...] = (
        EntityType.USERNAME,
        EntityType.ACCOUNT,
        EntityType.EMAIL,
        EntityType.PHONE,
        EntityType.URL,
        EntityType.DOMAIN,
        EntityType.ORGANIZATION,
        EntityType.LOCATION,
        EntityType.ADDRESS,
        EntityType.IP,
    )

    def _person_profile_candidates(
        self,
        person: Any,
        *,
        excluded_ids: set[str],
        review_decisions: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Return bounded, already-persisted OSINT entities suitable for review.

        These are candidates only.  Nothing is linked to the PERSON until the
        analyst explicitly chooses an item in the Person page.
        """

        entity_service = getattr(self._container, "entity_service", None)
        if entity_service is None:
            return []
        try:
            total = int(
                entity_service.count_all(
                    case_id=getattr(person, "case_id"),
                    entity_types=self.PROFILE_CANDIDATE_TYPES,
                )
            )
            rows = list(
                entity_service.get_page(
                    limit=500,
                    offset=max(0, total - 500),
                    case_id=getattr(person, "case_id"),
                    entity_types=self.PROFILE_CANDIDATE_TYPES,
                )
                or []
            )
        except TypeError:
            # Compatibility fallback for older service doubles.
            try:
                rows = list(entity_service.get_case_entities(getattr(person, "case_id")) or [])[:500]
            except Exception:
                return []
        except Exception:
            LOGGER.debug("Unable to load PERSON profile candidates", exc_info=True)
            return []

        candidates: list[dict[str, Any]] = []
        person_id = str(getattr(person, "id", "") or "")
        decisions = dict(review_decisions or {})

        relationship_service = getattr(
            self._container,
            "relationship_service",
            None,
        )
        corroboration_service = None
        calibration_service = (
            IdentityConfidenceCalibrationService()
        )
        case_relationships: list[Any] = []

        if (
            relationship_service is not None
            and entity_service is not None
        ):
            corroboration_service = (
                IdentityRelationshipCorroborationService(
                    relationship_service=relationship_service,
                    entity_service=entity_service,
                )
            )
            try:
                case_relationships = list(
                    relationship_service
                    .get_case_relationships(
                        getattr(person, "case_id")
                    )
                    or []
                )
            except Exception:
                LOGGER.debug(
                    "Unable to load relationships for identity corroboration",
                    exc_info=True,
                )
                case_relationships = []

        for candidate in rows:
            candidate_id = str(getattr(candidate, "id", "") or "")
            if not candidate_id or candidate_id == person_id or candidate_id in excluded_ids:
                continue
            candidate_type = str(
                getattr(
                    getattr(candidate, "entity_type", None),
                    "value",
                    getattr(candidate, "entity_type", "other"),
                )
            ).strip().lower()
            if candidate_type not in {item.value for item in self.PROFILE_CANDIDATE_TYPES}:
                continue
            metadata = self._metadata_dict(getattr(candidate, "metadata_json", None))
            workflow = str(metadata.get("workflow") or "").strip().lower()
            # Only surface data that actually came from stored OSINT / finding
            # provenance.  Manual attachments remain visible through the
            # existing profile sections and are not duplicated here.
            looks_osint = (
                workflow == "osint_enrichment"
                or bool(metadata.get("connector"))
                or bool(metadata.get("finding_source"))
                or bool(metadata.get("evidence_id"))
                or bool(metadata.get("finding_url"))
            )
            if not looks_osint:
                continue

            value = str(getattr(candidate, "value", "") or "")
            explicit_url = self._explicit_url_from_entity_values(
                entity_type=candidate_type,
                value=value,
                metadata=metadata,
            )

            base_confidence_value = (
                self._safe_optional_float(
                    getattr(
                        candidate,
                        "confidence",
                        None,
                    )
                )
            )
            corroboration_result = None
            corroboration_payload: dict[str, Any] = {}

            if (
                corroboration_service is not None
                and candidate_type
                in {
                    EntityType.USERNAME.value,
                    EntityType.ACCOUNT.value,
                    EntityType.URL.value,
                    EntityType.DOMAIN.value,
                }
            ):
                try:
                    corroboration_result = (
                        corroboration_service
                        .assess(
                            person=person,
                            candidate=candidate,
                            relationships=case_relationships,
                            base_confidence=(
                                base_confidence_value
                                if base_confidence_value is not None
                                else 0.0
                            ),
                        )
                    )
                    corroboration_payload = (
                        corroboration_result
                        .to_payload()
                    )
                except Exception:
                    LOGGER.debug(
                        "Unable to calculate relationship corroboration for %s",
                        candidate_id,
                        exc_info=True,
                    )

            identity_resolution = (
                self._identity_resolution_from_metadata(
                    metadata
                )
            )
            review_state = decisions.get(
                candidate_id,
                {},
            )
            calibration = calibration_service.calibrate(
                base_confidence=(
                    base_confidence_value
                    if base_confidence_value is not None
                    else 0.0
                ),
                identity_resolution=identity_resolution,
                relationship_result=corroboration_result,
                analyst_decision=str(
                    review_state.get(
                        "decision",
                        "unreviewed",
                    )
                ),
            )
            calibration_payload = calibration.to_payload()
            effective_confidence_value = (
                calibration.calibrated_confidence
            )

            candidates.append(
                {
                    "id": candidate_id,
                    "type": candidate_type,
                    "typeLabel": candidate_type.replace("_", " ").title(),
                    "value": value,
                    "confidence": self._confidence_text(
                        base_confidence_value
                    ),
                    "baseConfidence": self._confidence_text(
                        base_confidence_value
                    ),
                    "effectiveConfidence": self._confidence_text(
                        effective_confidence_value
                    ),
                    "calibratedConfidence": self._confidence_text(
                        calibration.calibrated_confidence
                    ),
                    "calibrationLabel": str(
                        calibration_payload.get(
                            "machineLabel",
                            "",
                        )
                    ),
                    "calibrationSummary": str(
                        calibration_payload.get(
                            "summary",
                            "",
                        )
                    ),
                    "calibrationIdentitySupport": round(
                        float(
                            calibration.identity_support
                        )
                        * 100.0,
                        1,
                    ),
                    "calibrationRelationshipSupport": round(
                        float(
                            calibration.relationship_support
                        )
                        * 100.0,
                        1,
                    ),
                    "calibrationConflictPenalty": round(
                        float(
                            calibration.conflict_penalty
                        )
                        * 100.0,
                        1,
                    ),
                    "calibrationHardConflict": bool(
                        calibration.hard_conflict
                    ),
                    "calibrationReviewRequired": bool(
                        calibration.review_required
                    ),
                    "calibrationPivotAllowed": bool(
                        calibration.pivot_allowed
                    ),
                    "calibrationPositiveSignals": list(
                        calibration.positive_signals
                    ),
                    "calibrationNegativeSignals": list(
                        calibration.negative_signals
                    ),
                    "socialEffectiveConfidence": self._confidence_text(
                        self._safe_optional_float(
                            corroboration_payload.get(
                                "effectiveConfidence"
                            )
                        )
                        if corroboration_payload
                        else base_confidence_value
                    ),
                    "relationshipBoost": round(
                        float(
                            corroboration_payload.get(
                                "boost",
                                0.0,
                            )
                            or 0.0
                        )
                        * 100.0,
                        1,
                    ),
                    "relationshipSupport": round(
                        float(
                            corroboration_payload.get(
                                "support",
                                0.0,
                            )
                            or 0.0
                        )
                        * 100.0,
                        1,
                    ),
                    "relationshipSummary": str(
                        corroboration_payload.get(
                            "summary",
                            ""
                        )
                        or ""
                    ),
                    "relationshipSignals": list(
                        corroboration_payload.get(
                            "signals",
                            []
                        )
                        or []
                    ),
                    "relationshipSuppressedCircular": int(
                        corroboration_payload.get(
                            "suppressedCircular",
                            0,
                        )
                        or 0
                    ),
                    "connector": str(metadata.get("connector") or ""),
                    "source": str(metadata.get("finding_source") or metadata.get("source") or ""),
                    "origin": str(metadata.get("origin_target_value") or ""),
                    "url": explicit_url,
                    "evidenceId": str(metadata.get("evidence_id") or ""),
                    "createdAt": self._date_text(getattr(candidate, "created_at", None)),
                    "reviewStatus": str(
                        decisions.get(
                            candidate_id,
                            {},
                        ).get(
                            "decision",
                            "unreviewed",
                        )
                    ),
                    "reviewLabel": str(
                        decisions.get(
                            candidate_id,
                            {},
                        ).get(
                            "label",
                            "Unreviewed",
                        )
                    ),
                    "reviewNote": str(
                        decisions.get(
                            candidate_id,
                            {},
                        ).get(
                            "note",
                            "",
                        )
                    ),
                    "reviewedAt": str(
                        decisions.get(
                            candidate_id,
                            {},
                        ).get(
                            "reviewedAt",
                            "",
                        )
                    ),
                    "reviewHistoryCount": int(
                        decisions.get(
                            candidate_id,
                            {},
                        ).get(
                            "historyCount",
                            0,
                        )
                        or 0
                    ),
                }
            )

        candidates.sort(
            key=lambda item: (
                0 if item.get("url") else 1,
                str(item.get("typeLabel") or ""),
                str(item.get("value") or "").casefold(),
            )
        )
        return candidates[:150]

    def _person_graph_payload(
        self,
        person: Any,
        *,
        related_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a deliberately simple PERSON -> account graph.

        Only USERNAME / ACCOUNT identifiers are rendered as graph nodes.
        Phones, emails, URLs, domains, organisations and locations stay in the
        normal profile panels where they are easier to read.  Cross-person
        relationships are intentionally delegated to the dedicated Graph page.
        """

        person_id = str(getattr(person, "id", "") or "")
        nodes: list[dict[str, Any]] = [
            {
                "id": person_id,
                "label": str(getattr(person, "value", "") or "Person"),
                "type": EntityType.PERSON.value,
                "central": True,
                "avatarUrl": self._person_avatar_url(person_id),
                "url": "",
                "basis": "person",
            }
        ]
        edges: list[dict[str, Any]] = []
        seen: set[str] = {person_id}
        allowed_types = {EntityType.USERNAME.value, EntityType.ACCOUNT.value}

        for row in related_rows:
            if len(nodes) >= 9:
                break
            related_id = str(row.get("id") or "")
            entity_type = str(
                row.get("rawType") or row.get("type") or "other"
            ).strip().lower().replace(" ", "_")
            if (
                not related_id
                or related_id in seen
                or entity_type not in allowed_types
            ):
                continue

            nodes.append(
                {
                    "id": related_id,
                    "label": str(row.get("value") or "Account"),
                    "type": entity_type,
                    "central": False,
                    "avatarUrl": "",
                    "url": str(row.get("url") or ""),
                    "basis": str(row.get("basis") or "evidence"),
                }
            )
            edges.append(
                {
                    "source": person_id,
                    "target": related_id,
                    "label": "",
                    "type": "profile_account",
                    "profile": True,
                    "path": False,
                }
            )
            seen.add(related_id)

        return {
            "nodes": nodes,
            "edges": edges,
            "notice": (
                "Only usernames and accounts are shown in this map. "
                "Phones, emails, pages and other intelligence stay in the profile panels."
                if len(nodes) > 1
                else "Attach an existing username/account to place it on this person's map."
            ),
        }

    def _build_person_snapshot(self, entity: Any, *, include_candidates: bool = True) -> dict[str, Any]:
        metadata = self._metadata_dict(getattr(entity, "metadata_json", None))
        confidence = self._safe_optional_float(getattr(entity, "confidence", None))
        case_id = str(getattr(entity, "case_id", "") or "")
        case = self._case_by_id(case_id)

        evidence_rows: list[dict[str, Any]] = []
        # R13.23.1 PERSON MENTION SNAPSHOT
        mention_rows: list[dict[str, Any]] = []
        related_rows: list[dict[str, Any]] = []
        link_rows: list[dict[str, Any]] = []
        photo_rows: list[dict[str, Any]] = []
        file_rows: list[dict[str, Any]] = []
        seen_related: set[str] = set()
        seen_urls: set[str] = set()

        def add_url(url: str, *, label: str, value: str = "", source: str = "", evidence_title: str = "") -> None:
            normalized_url = self._normalized_external_url(url)
            if not normalized_url or normalized_url in seen_urls:
                return
            seen_urls.add(normalized_url)
            host = urlparse(normalized_url).netloc
            link_rows.append({
                "label": label or host or "External page",
                "value": value or normalized_url,
                "url": normalized_url,
                "source": source or host,
                "evidenceTitle": evidence_title,
            })

        for url in self._metadata_explicit_urls(metadata):
            add_url(
                url,
                label=str(metadata.get("connector") or metadata.get("finding_source") or "Profile / page"),
                value=str(getattr(entity, "value", "") or ""),
                source=str(metadata.get("finding_source") or metadata.get("source") or ""),
            )

        link_service = getattr(self._container, "evidence_link_service", None)
        entity_service = getattr(self._container, "entity_service", None)
        evidence_objects = []
        if link_service is not None:
            evidence_objects = list(
                link_service.get_evidence_objects_for_entity(getattr(entity, "id")) or []
            )[:100]

        identity_review_decisions = (
            PersonIdentityReviewService
            .latest_decisions_from_evidence(
                evidence_objects
            )
        )

        for evidence in evidence_objects:
            evidence_metadata = self._metadata_dict(getattr(evidence, "metadata_json", None))
            evidence_title = str(getattr(evidence, "title", "") or "Evidence")
            evidence_type = str(
                getattr(getattr(evidence, "evidence_type", None), "value", getattr(evidence, "evidence_type", "evidence"))
            )
            managed_path_obj = PersonAttachmentService.managed_file_path(
                str(getattr(evidence, "file_path", "") or "")
            )
            managed_path = str(managed_path_obj) if managed_path_obj is not None else ""
            evidence_workflow = str(evidence_metadata.get("workflow") or "")
            is_manual = evidence_workflow == "manual_person_attachment"
            is_profile_selection = evidence_workflow == "person_profile_selection"
            is_identity_review = evidence_workflow == "person_identity_review"
            preview_url = ""
            if evidence_type == "image" and managed_path_obj is not None and managed_path_obj.is_file():
                preview_url = QUrl.fromLocalFile(str(managed_path_obj)).toString()
            evidence_row = {
                "id": str(getattr(evidence, "id", "") or ""),
                "title": evidence_title,
                "type": evidence_type.replace("_", " ").title(),
                "detail": str(getattr(evidence, "description", "") or getattr(evidence, "value", "") or "Supporting evidence"),
                "date": self._date_text(getattr(evidence, "created_at", None)),
                "manual": bool(is_manual),
                "attachmentKind": str(evidence_metadata.get("attachment_kind") or ""),
                "managedPath": managed_path,
                "previewUrl": preview_url,
                "mimeType": str(getattr(evidence, "mime_type", "") or ""),
                "sha256": str(getattr(evidence, "sha256", "") or ""),
            }
            evidence_rows.append(evidence_row)
            if evidence_workflow == "person_mention_selection":
                raw_mention = evidence_metadata.get("mention")
                mention = raw_mention if isinstance(raw_mention, dict) else {}
                raw_signals = mention.get("signals") or []
                signals = [
                    str(item).strip()
                    for item in list(raw_signals)
                    if str(item or "").strip()
                ][:8] if isinstance(raw_signals, (list, tuple, set, frozenset)) else []
                try:
                    mention_score = float(mention.get("score") or 0.0)
                except (TypeError, ValueError):
                    mention_score = 0.0
                mention_rows.append({
                    "id": str(getattr(evidence, "id", "") or ""),
                    "title": str(mention.get("title") or evidence_title),
                    "detail": str(mention.get("detail") or ""),
                    "summary": str(mention.get("summary") or " · ".join(signals[:4])),
                    "url": self._normalized_external_url(str(mention.get("url") or "")) or "",
                    "source": str(mention.get("source") or "Corroborating mention"),
                    "signals": signals,
                    "score": round(max(0.0, min(100.0, mention_score)), 1),
                    "lane": str(mention.get("lane") or ""),
                    "status": str(mention.get("status") or "Corroborating mention"),
                    "date": self._date_text(getattr(evidence, "created_at", None)),
                    "basis": "analyst_selected",
                })
            if preview_url:
                photo_rows.append(dict(evidence_row))
            elif managed_path:
                file_rows.append(dict(evidence_row))
            for url in self._metadata_explicit_urls(evidence_metadata):
                finding = evidence_metadata.get("finding") if isinstance(evidence_metadata.get("finding"), dict) else {}
                add_url(
                    url,
                    label=str(finding.get("source") or evidence_metadata.get("connector") or "Profile / page"),
                    source=str(evidence_metadata.get("connector") or finding.get("source") or ""),
                    evidence_title=evidence_title,
                )

            if (
                is_identity_review
                or link_service is None
                or entity_service is None
            ):
                continue

            for association in list(link_service.get_entities_for_evidence(getattr(evidence, "id")) or [])[:100]:
                related_id = str(getattr(association, "entity_id", "") or "")
                if not related_id or related_id == str(getattr(entity, "id", "")) or related_id in seen_related:
                    continue
                try:
                    related = entity_service.get_entity(UUID(related_id))
                except Exception:
                    LOGGER.debug("Unable to resolve related entity %s", related_id, exc_info=True)
                    continue
                if related is None:
                    continue

                related_type = str(
                    getattr(getattr(related, "entity_type", None), "value", getattr(related, "entity_type", "other"))
                ).strip().lower()

                review_state = (
                    identity_review_decisions
                    .get(
                        related_id,
                        {},
                    )
                )
                review_decision = str(
                    review_state.get(
                        "decision",
                        "",
                    )
                )

                if (
                    related_type
                    in {
                        EntityType.USERNAME.value,
                        EntityType.ACCOUNT.value,
                        EntityType.URL.value,
                        EntityType.DOMAIN.value,
                    }
                    and review_decision
                    in {
                        "rejected",
                        "review",
                    }
                ):
                    continue

                seen_related.add(related_id)
                related_metadata = self._metadata_dict(getattr(related, "metadata_json", None))
                explicit_url = self._explicit_url_from_entity_values(
                    entity_type=related_type,
                    value=str(getattr(related, "value", "") or ""),
                    metadata=related_metadata,
                )
                related_rows.append({
                    "id": related_id,
                    "type": related_type.replace("_", " ").title(),
                    "rawType": related_type,
                    "value": str(getattr(related, "value", "") or ""),
                    "confidence": self._confidence_text(self._safe_optional_float(getattr(related, "confidence", None))),
                    "url": explicit_url,
                    "evidenceTitle": evidence_title,
                    "basis": (
                        "analyst_confirmed"
                        if review_decision == "confirmed"
                        else (
                            "analyst_selected"
                            if is_profile_selection
                            else ("manual" if is_manual else "evidence")
                        )
                    ),
                    "reviewStatus": (
                        review_decision
                        or "unreviewed"
                    ),
                })
                if explicit_url:
                    add_url(
                        explicit_url,
                        label=str(related_metadata.get("connector") or related_metadata.get("finding_source") or related_type.replace("_", " ").title()),
                        value=str(getattr(related, "value", "") or ""),
                        source=str(related_metadata.get("finding_source") or related_metadata.get("source") or ""),
                        evidence_title=evidence_title,
                    )

        metadata_rows = []
        for key, label in (
            ("connector", "Connector"),
            ("finding_source", "Finding source"),
            ("origin_target_type", "Origin target type"),
            ("origin_target_value", "Origin target"),
            ("telegram_id", "Telegram ID"),
            ("source", "Source"),
        ):
            value = metadata.get(key)
            if value not in (None, ""):
                metadata_rows.append({"label": label, "value": str(value)})

        reviewable_profile_types = {
            EntityType.USERNAME.value,
            EntityType.ACCOUNT.value,
            EntityType.URL.value,
            EntityType.DOMAIN.value,
        }

        excluded_profile_ids = {
            str(getattr(entity, "id", "") or "")
        }

        excluded_profile_ids.update(
            str(item.get("id") or "")
            for item in related_rows
            if (
                item.get("id")
                and str(
                    item.get("rawType")
                    or item.get("type")
                    or ""
                )
                .strip()
                .lower()
                .replace(" ", "_")
                not in reviewable_profile_types
            )
        )
        profile_candidates = (
            self._person_profile_candidates(
                entity,
                excluded_ids=excluded_profile_ids,
                review_decisions=identity_review_decisions,
            )
            if include_candidates
            else []
        )
        person_graph = self._person_graph_payload(
            entity,
            related_rows=related_rows,
        )

        snapshot = {
            "id": str(getattr(entity, "id", "") or ""),
            "title": str(getattr(entity, "value", "") or "Unnamed person"),
            "type": EntityType.PERSON.value,
            "typeLabel": "Person",
            "normalizedValue": str(getattr(entity, "normalized_value", "") or ""),
            "confidenceText": self._confidence_text(confidence),
            "description": str(getattr(entity, "description", "") or "Person entity discovered in investigation data."),
            "caseTitle": str(case.get("title") or "") if case else self.currentCaseTitle,
            "createdAt": self._date_text(getattr(entity, "created_at", None)),
            "updatedAt": self._date_text(getattr(entity, "updated_at", None)),
            "metadataRows": metadata_rows,
            "links": link_rows[:40],
            "photos": photo_rows[:40],
            "files": file_rows[:40],
            "avatarUrl": self._person_avatar_url(getattr(entity, "id", "")),
            "evidence": evidence_rows[:50],
            "mentions": mention_rows[:40],
            "relatedEntities": related_rows[:100],
            "profileCandidates": profile_candidates,
            "identityReview": {
                "confirmed": sum(
                    1
                    for item in identity_review_decisions.values()
                    if item.get("decision") == "confirmed"
                ),
                "review": sum(
                    1
                    for item in identity_review_decisions.values()
                    if item.get("decision") == "review"
                ),
                "rejected": sum(
                    1
                    for item in identity_review_decisions.values()
                    if item.get("decision") == "rejected"
                ),
                "historyEntries": sum(
                    int(item.get("historyCount") or 0)
                    for item in identity_review_decisions.values()
                ),
            },
            "personGraph": person_graph,
            "associationNotice": (
                "Profiles, pages and related identifiers below are surfaced only from "
                "shared supporting evidence or explicit source URLs. Their presence does "
                "not by itself prove account ownership or identity."
            ),
        }
        snapshot["unifiedProfile"] = build_unified_target_profile(snapshot)
        return snapshot


    def _person_avatar_url(self, entity_id: Any) -> str:
        """Return the newest managed person photo as a local QML URL."""

        normalized = str(entity_id or "").strip()
        if not normalized:
            return ""
        if normalized in self._avatar_cache:
            return self._avatar_cache[normalized]

        link_service = getattr(self._container, "evidence_link_service", None)
        getter = getattr(link_service, "get_image_evidence_for_entity", None)
        if not callable(getter):
            self._avatar_cache[normalized] = ""
            return ""

        try:
            rows = list(getter(UUID(normalized)) or [])
        except Exception:
            LOGGER.debug("Unable to load person avatar evidence for %s", normalized, exc_info=True)
            self._avatar_cache[normalized] = ""
            return ""

        def created_key(row: Any) -> str:
            value = getattr(row, "created_at", None)
            return value.isoformat() if hasattr(value, "isoformat") else str(value or "")

        rows.sort(key=created_key, reverse=True)
        for row in rows:
            path = PersonAttachmentService.managed_file_path(
                str(getattr(row, "file_path", "") or "")
            )
            if path is not None and path.is_file():
                url = QUrl.fromLocalFile(str(path)).toString()
                self._avatar_cache[normalized] = url
                return url

        self._avatar_cache[normalized] = ""
        return ""

    @staticmethod
    def _dashboard_person_summary(snapshot: dict[str, Any]) -> list[dict[str, str]]:
        """Build compact readable profile rows for Home without graph clutter."""

        rows: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add(label: str, value: Any) -> None:
            text = str(value or "").strip()
            if not text:
                return
            key = (label.casefold(), text.casefold())
            if key in seen:
                return
            seen.add(key)
            rows.append({"label": label, "value": text})

        for item in list(snapshot.get("relatedEntities") or []):
            raw_type = str(item.get("rawType") or "").strip().lower()
            if raw_type in {EntityType.USERNAME.value, EntityType.ACCOUNT.value}:
                continue
            labels = {
                EntityType.PHONE.value: "Phone",
                EntityType.EMAIL.value: "Email",
                EntityType.DOMAIN.value: "Domain",
                EntityType.URL.value: "Page",
                EntityType.ORGANIZATION.value: "Organization",
                EntityType.LOCATION.value: "Location",
                EntityType.ADDRESS.value: "Address",
                EntityType.IP.value: "IP",
            }
            add(labels.get(raw_type, str(item.get("type") or "Data")), item.get("value"))
            if len(rows) >= 10:
                break

        if len(rows) < 10:
            for item in list(snapshot.get("links") or []):
                add("Profile page", item.get("value") or item.get("url"))
                if len(rows) >= 10:
                    break

        if len(rows) < 10:
            for item in list(snapshot.get("metadataRows") or []):
                label = str(item.get("label") or "")
                if label in {"Telegram ID", "Source", "Connector"}:
                    add(label, item.get("value"))
                if len(rows) >= 10:
                    break

        return rows[:10]

    def _dashboard_graph_payload(self) -> dict[str, Any]:
        """Build the simplified person-centric Home intelligence card.

        Home shows exactly one PERSON plus their analyst-linked usernames /
        accounts.  Other attributes are returned as compact summary rows.
        Cross-person relationships and path analysis remain in the Graph page.
        """

        empty = {
            "nodes": [],
            "edges": [],
            "options": [],
            "focusId": "",
            "notice": "",
            "depth": 1,
            "pathStartId": "",
            "pathEndId": "",
            "pathFound": False,
            "pathLabel": "",
            "summary": [],
            "personTitle": "",
            "accountCount": 0,
        }
        if not self._current_case_id:
            return empty

        entity_service = getattr(self._container, "entity_service", None)
        people: list[Any] = []

        if entity_service is not None:
            try:
                case_uuid = UUID(self._current_case_id)
                try:
                    people = list(
                        entity_service.get_page(
                            limit=150,
                            offset=0,
                            case_id=case_uuid,
                            entity_types=(EntityType.PERSON,),
                        )
                        or []
                    )
                except TypeError:
                    getter = getattr(entity_service, "get_case_entities", None)
                    if callable(getter):
                        people = [
                            item
                            for item in list(getter(case_uuid) or [])
                            if str(
                                getattr(
                                    getattr(item, "entity_type", None),
                                    "value",
                                    getattr(item, "entity_type", ""),
                                )
                                or ""
                            ).strip().lower() == EntityType.PERSON.value
                        ]
            except Exception:
                LOGGER.exception("Unable to load Home PERSON options")
                return {**empty, "notice": "Person intelligence is temporarily unavailable."}
        else:
            workspace = self._current_workspace() or {}
            graph = workspace.get("graph", {}) or {}
            people = [
                dict(item)
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict)
                and str(item.get("type") or "").strip().lower() == EntityType.PERSON.value
            ]

        if not people:
            return {**empty, "notice": "No people are available in the selected investigation."}

        def person_id(item: Any) -> str:
            return str(item.get("id") if isinstance(item, dict) else getattr(item, "id", "") or "")

        def person_label(item: Any) -> str:
            return str(item.get("label") if isinstance(item, dict) else getattr(item, "value", "") or "Unnamed person")

        people.sort(key=lambda item: person_label(item).casefold())
        options = [
            {"id": person_id(item), "label": person_label(item), "type": EntityType.PERSON.value}
            for item in people
            if person_id(item)
        ]
        valid_ids = {item["id"] for item in options}

        focus_id = str(self._dashboard_focus_entity_id or "")
        preferred = str(self._current_entity_id or "")
        if focus_id not in valid_ids:
            focus_id = preferred if preferred in valid_ids else options[0]["id"]
            self._dashboard_focus_entity_id = focus_id

        if entity_service is None:
            focus = next((item for item in options if item["id"] == focus_id), options[0])
            return {
                **empty,
                "nodes": [{
                    "id": focus["id"],
                    "label": focus["label"],
                    "type": EntityType.PERSON.value,
                    "central": True,
                    "avatarUrl": "",
                }],
                "options": options,
                "focusId": focus["id"],
                "personTitle": focus["label"],
                "notice": "Profile details require the live entity service.",
            }

        try:
            person = entity_service.get_entity(UUID(focus_id))
            if person is None:
                return {**empty, "options": options, "notice": "The selected person no longer exists."}
            snapshot = self._build_person_snapshot(person, include_candidates=False)
        except Exception:
            LOGGER.exception("Unable to build Home PERSON intelligence snapshot")
            return {**empty, "options": options, "focusId": focus_id, "notice": "Person profile is temporarily unavailable."}

        person_graph = dict(snapshot.get("personGraph") or {})
        nodes = list(person_graph.get("nodes") or [])
        edges = list(person_graph.get("edges") or [])
        account_count = sum(
            1
            for item in nodes
            if str(item.get("type") or "").strip().lower()
            in {EntityType.USERNAME.value, EntityType.ACCOUNT.value}
        )

        return {
            **empty,
            "nodes": nodes,
            "edges": edges,
            "options": options,
            "focusId": focus_id,
            "notice": str(person_graph.get("notice") or ""),
            "summary": self._dashboard_person_summary(snapshot),
            "personTitle": str(snapshot.get("title") or person_label(person)),
            "accountCount": account_count,
        }

    def _ui_settings_payload(self) -> dict[str, Any]:
        defaults = {
            "showWorldMap": True,
            "showSlogan": True,
            "graphNodeLimit": 36,
            "graphDepth": 1,
            "graphEdgeLabels": False,
        }
        result: dict[str, Any] = {}
        for key, default in defaults.items():
            raw = self._desktop_settings.value(f"desktop_ui/{key}", default)
            if isinstance(default, bool):
                if isinstance(raw, str):
                    result[key] = raw.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    result[key] = bool(raw)
            elif isinstance(default, int):
                try:
                    result[key] = int(raw)
                except (TypeError, ValueError):
                    result[key] = default
            else:
                try:
                    result[key] = float(raw)
                except (TypeError, ValueError):
                    result[key] = default
        result["graphNodeLimit"] = min(80, max(12, int(result["graphNodeLimit"])))
        result["graphDepth"] = 2 if int(result["graphDepth"]) >= 2 else 1
        return result

    def _graph_workspace_payload(self) -> dict[str, Any]:
        """Return a bounded, UI-ready graph for the selected investigation."""
        empty = {
            "nodes": [], "edges": [], "allNodes": [], "options": [],
            "focusId": "", "focusLabel": "", "focusType": "",
            "notice": "Select an investigation to inspect its relationship graph.",
            "depth": int(self._ui_settings_payload().get("graphDepth") or 1),
            "statistics": {
                "nodeCount": 0, "edgeCount": 0, "isolatedNodes": 0,
                "connectedNodes": 0, "visibleNodes": 0, "visibleEdges": 0,
                "relationshipTypes": [],
            },
        }
        if not self._current_case_id:
            return empty

        graph_data: dict[str, Any] = {}
        graph_service = getattr(self._container, "entity_graph_service", None)
        if graph_service is not None:
            try:
                graph_data = graph_service.get_case_graph_data(UUID(self._current_case_id)) or {}
            except Exception:
                LOGGER.exception("Unable to build case graph data")
                return {**empty, "notice": "The relationship graph is temporarily unavailable."}
        else:
            graph_data = dict((self._current_workspace() or {}).get("graph") or {})

        raw_nodes = [dict(item) for item in list(graph_data.get("nodes") or []) if isinstance(item, dict)]
        raw_edges = [dict(item) for item in list(graph_data.get("edges") or []) if isinstance(item, dict)]
        if not raw_nodes:
            return {**empty, "notice": "No entities are available in the selected investigation yet."}

        node_map = {str(item.get("id") or ""): item for item in raw_nodes if str(item.get("id") or "")}
        adjacency: dict[str, set[str]] = {key: set() for key in node_map}
        for edge in raw_edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source in adjacency and target in adjacency:
                adjacency[source].add(target)
                adjacency[target].add(source)

        def degree_for(node_id: str) -> int:
            node = node_map[node_id]
            try:
                return int(node.get("degree") or len(adjacency.get(node_id, set())))
            except (TypeError, ValueError):
                return len(adjacency.get(node_id, set()))

        sorted_ids = sorted(
            node_map,
            key=lambda node_id: (-degree_for(node_id), str(node_map[node_id].get("label") or "").casefold(), node_id),
        )
        valid_ids = set(sorted_ids)
        preferred = str(self._graph_focus_entity_id or self._current_entity_id or "")
        focus_id = preferred if preferred in valid_ids else sorted_ids[0]
        self._graph_focus_entity_id = focus_id

        settings = self._ui_settings_payload()
        depth = int(settings.get("graphDepth") or 1)
        limit = int(settings.get("graphNodeLimit") or 36)
        selected: list[str] = [focus_id]
        seen = {focus_id}
        frontier = [focus_id]
        for _ in range(depth):
            candidates: list[str] = []
            for current_id in frontier:
                candidates.extend(adjacency.get(current_id, set()))
            candidates = sorted(
                {candidate for candidate in candidates if candidate not in seen},
                key=lambda node_id: (-degree_for(node_id), str(node_map[node_id].get("label") or "").casefold()),
            )
            if not candidates:
                break
            remaining = max(0, limit - len(selected))
            accepted = candidates[:remaining]
            selected.extend(accepted)
            seen.update(accepted)
            frontier = accepted
            if len(selected) >= limit:
                break

        if len(selected) == 1 and not adjacency.get(focus_id):
            selected.extend([node_id for node_id in sorted_ids if node_id != focus_id][: max(0, min(limit, 12) - 1)])

        visible_ids = set(selected)
        nodes: list[dict[str, Any]] = []
        for index, node_id in enumerate(selected):
            node = node_map[node_id]
            node_type = str(node.get("type") or "entity").strip().lower()
            nodes.append({
                "id": node_id, "label": str(node.get("label") or "Unnamed entity"),
                "type": node_type, "degree": degree_for(node_id), "central": index == 0,
                "avatarUrl": self._person_avatar_url(node_id) if node_type == EntityType.PERSON.value else "",
            })

        edges: list[dict[str, Any]] = []
        relationship_counts: Counter[str] = Counter()
        for edge in raw_edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            raw_type = str(edge.get("type") or "related_to").strip().lower()
            relationship_counts[raw_type] += 1
            if source not in visible_ids or target not in visible_ids:
                continue
            edges.append({
                "id": str(edge.get("id") or f"{source}:{target}:{raw_type}"),
                "source": source, "target": target,
                "label": raw_type.replace("_", " ").upper(),
                "confidence": edge.get("confidence", 1.0),
            })

        options = [
            {
                "id": node_id,
                "label": f"{str(node_map[node_id].get('label') or 'Unnamed entity')} · {str(node_map[node_id].get('type') or 'entity').replace('_', ' ')}",
                "type": str(node_map[node_id].get("type") or "entity").strip().lower(),
            }
            for node_id in sorted_ids[:500]
        ]
        isolated = sum(1 for node_id in node_map if not adjacency.get(node_id))
        focus = node_map[focus_id]
        notice = ""
        if not raw_edges:
            notice = "Entities exist, but no persisted relationships have been recorded yet."
        elif len(node_map) > len(selected):
            notice = f"Showing {len(selected)} of {len(node_map)} entities around the selected focus."

        return {
            **empty, "nodes": nodes, "edges": edges,
            "allNodes": [
                {
                    "id": node_id, "label": str(node_map[node_id].get("label") or "Unnamed entity"),
                    "type": str(node_map[node_id].get("type") or "entity").strip().lower(),
                    "degree": degree_for(node_id),
                }
                for node_id in sorted_ids
            ],
            "options": options, "focusId": focus_id,
            "focusLabel": str(focus.get("label") or "Unnamed entity"),
            "focusType": str(focus.get("type") or "entity").replace("_", " ").title(),
            "notice": notice, "depth": depth,
            "statistics": {
                "nodeCount": len(node_map), "edgeCount": len(raw_edges),
                "isolatedNodes": isolated, "connectedNodes": len(node_map) - isolated,
                "visibleNodes": len(nodes), "visibleEdges": len(edges),
                "relationshipTypes": [
                    {"label": key.replace("_", " ").title(), "count": count}
                    for key, count in relationship_counts.most_common(8)
                ],
            },
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
                "id": str(item.get("id") or ""),
                "page": "entities",
                "headline": str(item.get("value") or "Unnamed entity"),
                "detail": f"{str(item.get('type') or 'entity').replace('_', ' ').title()} added to an investigation",
                "timeText": self._date_text(item.get("created_at") or item.get("updated_at")),
                "icon": "users_purple.svg",
                "color": "#a98be9",
            }))
        for item in evidence:
            rows.append((str(item.get("created_at") or item.get("updated_at") or ""), {
                "id": str(item.get("id") or ""),
                "page": "evidence",
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
