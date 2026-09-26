from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Property, QThread, Signal, Slot

from app.application.person_mention_selection_service import (
    PersonMentionSelectionService,
)
from app.models.entity import EntityType

from app.interface.desktop.workers.unified_investigation_search_worker import (
    UnifiedInvestigationSearchWorker,
)
from app.interface.desktop.workers.account_enrichment_worker import (
    AccountEnrichmentWorker,
)
from app.interface.desktop.workers.public_social_activity_worker import (
    PublicSocialActivityWorker,
)
from app.application.public_social_activity import PublicSocialActivityCollector
from app.application.social_content_correlation import (
    build_social_intelligence,
    correlate_social_content,
)
from app.osint.connectors.maigret_connector import MaigretConnector


LOGGER = logging.getLogger(__name__)


class InvestigationSearchBridge(QObject):
    """QML bridge for R13.20 structured all-source investigation search."""

    changed = Signal()
    messageChanged = Signal()
    accountEnrichmentChanged = Signal()
    socialActivityChanged = Signal()

    def __init__(self, container: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._run: dict[str, Any] = {}
        self._busy = False
        self._message = ""
        self._thread: QThread | None = None
        self._worker: UnifiedInvestigationSearchWorker | None = None
        self._context: dict[str, Any] = {}
        self._account_enrichment: dict[str, Any] = {}
        self._account_busy = False
        self._account_thread: QThread | None = None
        self._account_worker: AccountEnrichmentWorker | None = None
        self._account_context: dict[str, Any] = {}
        self._social_activity: dict[str, Any] = {}
        self._social_busy = False
        self._social_thread: QThread | None = None
        self._social_worker: PublicSocialActivityWorker | None = None

    @Property("QVariantMap", notify=changed)
    def runData(self) -> dict[str, Any]:
        return dict(self._run)

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=messageChanged)
    def message(self) -> str:
        return self._message

    @Property("QVariantMap", notify=accountEnrichmentChanged)
    def accountEnrichment(self) -> dict[str, Any]:
        return dict(self._account_enrichment)

    @Property(bool, notify=accountEnrichmentChanged)
    def accountEnrichmentBusy(self) -> bool:
        return self._account_busy

    @Property("QVariantMap", notify=socialActivityChanged)
    def socialActivity(self) -> dict[str, Any]:
        return dict(self._social_activity)

    @Property(bool, notify=socialActivityChanged)
    def socialActivityBusy(self) -> bool:
        return self._social_busy

    @Slot("QVariantMap", str, "QVariantMap", str, result=bool)
    def search(
        self,
        profile: object,
        case_id: str,
        options: object = None,
        person_entity_id: str = "",
    ) -> bool:
        if self._busy or self._account_busy or self._social_busy:
            self._set_message(
                "Another investigation or account-enrichment task is already running."
            )
            return False

        normalized_case_id = str(case_id or "").strip()
        if not normalized_case_id:
            self._set_message("Select an investigation before running all-source search.")
            return False

        normalized_person_id = str(
            person_entity_id
            or ""
        ).strip()
        if not normalized_person_id:
            self._set_message(
                "Select the person these search results belong to."
            )
            return False

        entity_service = getattr(
            self._container,
            "entity_service",
            None,
        )
        if entity_service is None:
            self._set_message(
                "PERSON selection is unavailable because the entity service is not configured."
            )
            return False

        try:
            case_uuid = UUID(
                normalized_case_id
            )
            person = entity_service.get_entity(
                UUID(normalized_person_id)
            )
        except Exception as exc:
            LOGGER.exception(
                "Unable to resolve PERSON search target"
            )
            self._set_message(
                f"Unable to resolve selected person: {exc}"
            )
            return False

        if person is None:
            self._set_message(
                "The selected person no longer exists."
            )
            return False

        person_type = str(
            getattr(
                getattr(
                    person,
                    "entity_type",
                    None,
                ),
                "value",
                getattr(
                    person,
                    "entity_type",
                    "",
                ),
            )
            or ""
        ).strip().lower()

        if person_type != EntityType.PERSON.value:
            self._set_message(
                "The selected search target must be a person."
            )
            return False

        if getattr(
            person,
            "case_id",
            None,
        ) != case_uuid:
            self._set_message(
                "The selected person belongs to a different investigation."
            )
            return False

        payload = dict(profile) if isinstance(profile, dict) else {}
        settings = dict(options) if isinstance(options, dict) else {}
        if not self._has_input(payload):
            self._set_message("Enter at least one known data point before searching.")
            return False

        self._account_enrichment = {}
        self._social_activity = {}
        self.accountEnrichmentChanged.emit()
        self.socialActivityChanged.emit()
        started_at = datetime.now()
        self._context = {
            "caseId": normalized_case_id,
            "startedAt": started_at,
            "profile": payload,
            "options": settings,
            "personEntityId": normalized_person_id,
            "personLabel": str(
                getattr(
                    person,
                    "value",
                    "",
                )
                or "Person"
            ),
        }
        self._run = {
            "hasRun": True,
            "status": "running",
            "phase": "planning",
            "progressText": "Building search plan…",
            "results": [],
            "providers": [],
            "pivots": [],
            "errors": [],
            "seeds": [],
            "summary": {
                "seeds": 0,
                "results": 0,
                "providers": 0,
                "pivots": 0,
                "errors": 0,
                "guarded": 0,
                "evidenceCreated": 0,
                "entitiesCreated": 0,
            },
            "startedLabel": started_at.strftime("%b %d, %Y · %H:%M:%S"),
            "durationText": "Running…",
            "error": "",
            "personTarget": {
                "id": normalized_person_id,
                "label": str(
                    getattr(
                        person,
                        "value",
                        "",
                    )
                    or "Person"
                ),
            },
            "rawSecretValuesStored": False,
        }
        self._busy = True
        self._set_message("Unified investigation search started.")
        self.changed.emit()

        try:
            thread = QThread(self)
            worker = UnifiedInvestigationSearchWorker(
                case_id=normalized_case_id,
                profile=payload,
                options=settings,
                person_entity_id=normalized_person_id,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._on_progress)
            worker.succeeded.connect(self._on_succeeded)
            worker.failed.connect(self._on_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_thread_finished)
            thread.finished.connect(thread.deleteLater)
            self._thread = thread
            self._worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start unified investigation worker")
            self._busy = False
            self._thread = None
            self._worker = None
            self._context = {}
            self._run.update(
                {
                    "status": "failed",
                    "error": str(exc),
                    "durationText": "0.0s",
                }
            )
            self._set_message(f"Unable to start investigation search: {exc}")
            self.changed.emit()
            return False

    @Slot()
    def clear(self) -> None:
        if self._busy or self._account_busy or self._social_busy:
            return
        self._run = {}
        self._account_enrichment = {}
        self._social_activity = {}
        self._set_message("")
        self.changed.emit()
        self.accountEnrichmentChanged.emit()
        self.socialActivityChanged.emit()

    @Slot()
    def clearAccountEnrichment(self) -> None:
        if self._account_busy:
            return
        self._account_enrichment = {}
        self._account_context = {}
        self.accountEnrichmentChanged.emit()

    @Slot()
    def clearSocialActivity(self) -> None:
        if self._social_busy:
            return
        self._social_activity = {}
        self.socialActivityChanged.emit()

    @Slot("QVariantMap", result="QVariantMap")
    def socialActivityCapability(self, account: object) -> dict[str, Any]:
        payload = dict(account) if isinstance(account, dict) else {}
        return PublicSocialActivityCollector.capability(payload)

    @Slot("QVariantMap", result=bool)
    def collectPublicActivity(self, account: object) -> bool:
        if self._busy or self._account_busy or self._social_busy:
            self._set_message("Another investigation task is already running.")
            return False

        payload = dict(account) if isinstance(account, dict) else {}
        capability = PublicSocialActivityCollector.capability(payload)
        if not capability.get("available"):
            self._set_message(str(capability.get("reason") or "Public activity collection is unavailable."))
            return False

        person_target = self._run.get("personTarget")
        person_target = person_target if isinstance(person_target, dict) else {}
        person_id = str(person_target.get("id") or "").strip()
        if not person_id:
            self._set_message("Run the search for a selected person before collecting account activity.")
            return False

        self._social_activity = {
            "hasRun": True,
            "status": "running",
            "platform": str(capability.get("platform") or ""),
            "username": str(capability.get("username") or ""),
            "items": [],
            "correlations": [],
            "error": "",
            "durationText": "Running…",
        }
        self._social_busy = True
        self._set_message(
            "Collecting public activity for @"
            + str(capability.get("username") or "")
            + "…"
        )
        self.socialActivityChanged.emit()

        try:
            thread = QThread(self)
            worker = PublicSocialActivityWorker(
                account=payload,
                person_entity_id=person_id,
                limit=50,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_social_activity_succeeded)
            worker.failed.connect(self._on_social_activity_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_social_activity_thread_finished)
            thread.finished.connect(thread.deleteLater)
            self._social_thread = thread
            self._social_worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start public social activity worker")
            self._social_busy = False
            self._social_thread = None
            self._social_worker = None
            self._social_activity.update(
                {
                    "status": "failed",
                    "error": str(exc),
                    "durationText": "0.0s",
                }
            )
            self._set_message(f"Unable to collect public activity: {exc}")
            self.socialActivityChanged.emit()
            return False

    @Slot(object)
    def _on_social_activity_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        data = dict(snapshot)
        data.update(
            {
                "hasRun": True,
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": str(snapshot.get("error") or ""),
            }
        )
        self._social_activity = data

        new_items = list(data.get("items") or [])
        existing = list(self._run.get("socialContent") or [])
        combined = []
        seen = set()
        for item in existing + new_items:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("platform") or "").casefold(),
                str(item.get("author") or "").casefold(),
                str(item.get("url") or ""),
                str(item.get("timestamp") or ""),
                str(item.get("text") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            combined.append(dict(item))
        if self._run:
            intelligence = build_social_intelligence(combined)
            self._run["socialContent"] = combined[:500]
            self._run["socialCorrelations"] = list(
                intelligence.get("correlations") or []
            )[:200]
            self._run["socialIntelligence"] = intelligence
            summary = dict(self._run.get("summary") or {})
            summary["socialContent"] = len(combined)
            summary["socialCorrelations"] = len(self._run["socialCorrelations"])
            summary["socialAuthors"] = int(
                (intelligence.get("summary") or {}).get("authors") or 0
            )
            summary["socialPlatforms"] = int(
                (intelligence.get("summary") or {}).get("platforms") or 0
            )
            summary["socialSignals"] = int(
                (intelligence.get("summary") or {}).get("signals") or 0
            )
            self._run["summary"] = summary
            self.changed.emit()

        persistence = data.get("persistence")
        persistence = persistence if isinstance(persistence, dict) else {}
        self._set_message(
            "Public activity collected: "
            f"{int(data.get('count') or 0)} item(s), "
            f"{int(persistence.get('created') or 0)} new evidence item(s)."
        )
        self.socialActivityChanged.emit()

    @Slot(object)
    def _on_social_activity_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Public activity collection failed.")
        duration = self._safe_float(payload.get("duration"))
        self._social_activity = {
            "hasRun": True,
            "status": "failed",
            "items": [],
            "correlations": [],
            "error": error,
            "durationSeconds": round(duration, 3),
            "durationText": f"{duration:.1f}s",
        }
        self._set_message(f"Public activity collection failed: {error}")
        self.socialActivityChanged.emit()

    @Slot()
    def _on_social_activity_thread_finished(self) -> None:
        self._social_busy = False
        self._social_worker = None
        self._social_thread = None
        self.socialActivityChanged.emit()

    @Slot("QVariantMap", result="QVariantMap")
    def accountEnrichmentCapability(self, account: object) -> dict[str, Any]:
        payload = dict(account) if isinstance(account, dict) else {}
        if not payload:
            return {
                "available": False,
                "reason": "The selected account payload is unavailable.",
                "site": "",
                "username": "",
            }

        username = self._account_username(payload)
        observation = self._preferred_maigret_observation(payload)
        site = str(observation.get("service") or payload.get("service") or "").strip()
        profile_url = str(observation.get("url") or payload.get("url") or "").strip()
        if not username:
            return {
                "available": False,
                "reason": "Unable to determine the username for this account.",
                "site": "",
                "username": "",
            }
        if not site:
            return {
                "available": False,
                "reason": "The provider did not expose a platform name for targeted enrichment.",
                "site": "",
                "username": username,
            }

        resolution = MaigretConnector.resolve_deep_site(
            username=username,
            suggested_site=site,
            profile_url=profile_url,
        )
        return {
            "available": bool(resolution.get("supported")),
            "reason": str(resolution.get("reason") or ""),
            "site": str(resolution.get("site") or ""),
            "username": username,
            "profileUrl": profile_url,
            "requestedSite": site,
        }

    @Slot("QVariantMap", result=bool)
    def deepEnrichAccount(self, account: object) -> bool:
        if self._busy or self._account_busy or self._social_busy:
            self._set_message("Another search or account enrichment is already running.")
            return False

        payload = dict(account) if isinstance(account, dict) else {}
        if not payload:
            self._set_message("The selected account payload is unavailable.")
            return False

        username = self._account_username(payload)
        observation = self._preferred_maigret_observation(payload)
        site = str(observation.get("service") or payload.get("service") or "").strip()
        profile_url = str(observation.get("url") or payload.get("url") or "").strip()

        if not username:
            self._set_message("Unable to determine the username for this account.")
            return False
        if not site:
            self._set_message(
                "This account does not expose a Maigret site name for targeted enrichment."
            )
            return False

        self._account_context = {
            "username": username,
            "site": site,
            "profileUrl": profile_url,
        }
        self._account_enrichment = {
            "hasRun": True,
            "status": "running",
            "username": username,
            "site": site,
            "profileUrl": profile_url,
            "fields": [],
            "observations": [],
            "error": "",
            "durationText": "Running…",
        }
        self._account_busy = True
        self._set_message(f"Deep-enriching {username} on {site}…")
        self.accountEnrichmentChanged.emit()

        try:
            thread = QThread(self)
            worker = AccountEnrichmentWorker(
                username=username,
                site=site,
                profile_url=profile_url,
                timeout=25,
            )
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.succeeded.connect(self._on_account_enrichment_succeeded)
            worker.failed.connect(self._on_account_enrichment_failed)
            worker.succeeded.connect(thread.quit)
            worker.failed.connect(thread.quit)
            worker.succeeded.connect(worker.deleteLater)
            worker.failed.connect(worker.deleteLater)
            thread.finished.connect(self._on_account_enrichment_thread_finished)
            thread.finished.connect(thread.deleteLater)
            self._account_thread = thread
            self._account_worker = worker
            thread.start()
            return True
        except Exception as exc:
            LOGGER.exception("Unable to start account enrichment worker")
            self._account_busy = False
            self._account_thread = None
            self._account_worker = None
            self._account_context = {}
            self._account_enrichment.update(
                {
                    "status": "failed",
                    "error": str(exc),
                    "durationText": "0.0s",
                }
            )
            self._set_message(f"Unable to start account enrichment: {exc}")
            self.accountEnrichmentChanged.emit()
            return False

    @Slot(object)
    def _on_account_enrichment_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        data = dict(snapshot)
        data.update(
            {
                "hasRun": True,
                "status": str(snapshot.get("status") or "success"),
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": str(snapshot.get("error") or ""),
            }
        )
        self._account_enrichment = data
        self._set_message(
            f"Account enrichment completed for {data.get('username') or ''} on {data.get('site') or ''}."
        )
        self.accountEnrichmentChanged.emit()

    @Slot(object)
    def _on_account_enrichment_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        error = str(payload.get("error") or snapshot.get("error") or "Account enrichment failed.")
        data = dict(snapshot)
        data.update(
            {
                "hasRun": True,
                "status": str(snapshot.get("status") or "failed"),
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": error,
            }
        )
        self._account_enrichment = data
        if str(data.get("status") or "").casefold() in {"not_supported", "not_available"}:
            self._set_message(error)
        else:
            self._set_message(f"Account enrichment failed: {error}")
        self.accountEnrichmentChanged.emit()

    @Slot()
    def _on_account_enrichment_thread_finished(self) -> None:
        self._account_busy = False
        self._account_worker = None
        self._account_thread = None
        self._account_context = {}
        self.accountEnrichmentChanged.emit()

    @staticmethod
    def _account_username(payload: dict[str, Any]) -> str:
        identifiers = payload.get("identifiers")
        if isinstance(identifiers, dict):
            for key in ("username", "handle", "user_name"):
                value = str(identifiers.get(key) or "").strip().lstrip("@")
                if value:
                    return value
        if str(payload.get("seedType") or "").strip().casefold() == "username":
            value = str(payload.get("seed") or "").strip().lstrip("@")
            if value:
                return value
        return str(payload.get("title") or "").strip().lstrip("@")

    @staticmethod
    def _preferred_maigret_observation(payload: dict[str, Any]) -> dict[str, Any]:
        observations = payload.get("accountObservations")
        if not isinstance(observations, list):
            observations = []
        for item in observations:
            if not isinstance(item, dict):
                continue
            if str(item.get("connector") or "").strip().casefold() == "maigret" and str(item.get("service") or "").strip():
                return dict(item)
        for item in observations:
            if isinstance(item, dict) and str(item.get("service") or "").strip():
                return dict(item)
        return {}

    @Slot(object)
    def _on_progress(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        current = dict(self._run)
        if not current:
            return
        current["phase"] = str(payload.get("phase") or "running")
        current["progressText"] = str(payload.get("detail") or "Searching…")
        summary = dict(current.get("summary") or {})
        for source_key, target_key in (
            ("seeds", "seeds"),
            ("pivots", "pivots"),
            ("providers", "providers"),
        ):
            if source_key in payload:
                summary[target_key] = int(payload.get(source_key) or 0)
        if "targetsProcessed" in payload:
            summary["targetsProcessed"] = int(payload.get("targetsProcessed") or 0)
        if "queuedTargets" in payload:
            summary["queuedTargets"] = int(payload.get("queuedTargets") or 0)
        current["summary"] = summary
        self._run = current
        self._set_message(str(payload.get("detail") or "Unified search running…"))
        self.changed.emit()

    @Slot(object)
    def _on_succeeded(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        duration = self._safe_float(payload.get("duration"))
        started_at = self._context.get("startedAt")
        run = dict(snapshot)
        run.update(
            {
                "hasRun": True,
                "caseId": str(self._context.get("caseId") or ""),
                "phase": "completed",
                "progressText": "All selected source layers completed.",
                "startedLabel": (
                    started_at.strftime("%b %d, %Y · %H:%M:%S")
                    if isinstance(started_at, datetime)
                    else ""
                ),
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": "",
                "rawSecretValuesStored": False,
            }
        )
        self._run = run
        summary = dict(run.get("summary") or {})
        self._set_message(
            "Investigation search completed: "
            f"{int(summary.get('results') or 0)} result(s), "
            f"{int(summary.get('pivots') or 0)} new exact pivot(s), "
            f"{int(summary.get('evidenceCreated') or 0)} evidence item(s) persisted."
        )
        self.changed.emit()

    @Slot(object)
    def _on_failed(self, result: object) -> None:
        payload = result if isinstance(result, dict) else {}
        error = str(payload.get("error") or "Unknown investigation search error")
        duration = self._safe_float(payload.get("duration"))
        self._run.update(
            {
                "hasRun": True,
                "status": "failed",
                "phase": "failed",
                "progressText": error,
                "durationSeconds": round(duration, 3),
                "durationText": f"{duration:.1f}s",
                "error": error,
                "rawSecretValuesStored": False,
            }
        )
        self._set_message(f"Investigation search failed: {error}")
        self.changed.emit()

    @Slot()
    def _on_thread_finished(self) -> None:
        self._busy = False
        self._worker = None
        self._thread = None
        self._context = {}
        self.changed.emit()

    @staticmethod
    def _has_input(payload: dict[str, Any]) -> bool:
        ignored = {"notes", "birthDate", "country", "region", "city", "postalCode"}
        for key, value in payload.items():
            if key in ignored:
                continue
            if isinstance(value, (list, tuple, set, frozenset)):
                if any(str(item or "").strip() for item in value):
                    return True
            elif str(value or "").strip():
                return True
        # Address plus location is also a valid seed.
        return bool(str(payload.get("address") or "").strip())

    # R13.23.1 PERSON MENTION ACTIONS
    @Slot(str, result="QVariantList")
    def personOptions(self, case_id: str) -> list[dict[str, str]]:
        normalized = str(case_id or "").strip()
        if not normalized:
            return []
        entity_service = getattr(self._container, "entity_service", None)
        if entity_service is None:
            return []
        try:
            case_uuid = UUID(normalized)
        except (TypeError, ValueError, AttributeError):
            return []

        try:
            try:
                rows = list(
                    entity_service.get_page(
                        limit=250,
                        offset=0,
                        case_id=case_uuid,
                        entity_types=(EntityType.PERSON,),
                    )
                    or []
                )
            except TypeError:
                rows = [
                    item
                    for item in list(entity_service.get_case_entities(case_uuid) or [])
                    if str(
                        getattr(
                            getattr(item, "entity_type", None),
                            "value",
                            getattr(item, "entity_type", ""),
                        )
                        or ""
                    ) == EntityType.PERSON.value
                ]
        except Exception:
            LOGGER.exception("Unable to load person options for mention selection")
            return []

        result = [
            {
                "id": str(getattr(item, "id", "") or ""),
                "label": str(getattr(item, "value", "") or "Unnamed person"),
            }
            for item in rows
            if getattr(item, "id", None) is not None
        ]
        result.sort(key=lambda item: (item["label"].casefold(), item["id"]))
        return result

    @Slot(str, "QVariantMap", result="QVariantMap")
    def addMentionToPerson(self, person_id: str, mention: object) -> dict[str, Any]:
        normalized_person_id = str(person_id or "").strip()
        payload = dict(mention) if isinstance(mention, dict) else {}
        if not normalized_person_id:
            return {"ok": False, "error": "Select a person first."}
        if not payload:
            return {"ok": False, "error": "The mention payload is unavailable."}

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
            return {"ok": False, "error": "Mention persistence services are unavailable."}

        try:
            person = entity_service.get_entity(UUID(normalized_person_id))
        except Exception as exc:
            LOGGER.exception("Unable to resolve PERSON for corroborating mention")
            return {"ok": False, "error": f"Unable to resolve person: {exc}"}
        if person is None:
            return {"ok": False, "error": "The selected person no longer exists."}

        run_case_id = str(self._run.get("caseId") or "").strip()
        person_case_id = str(getattr(person, "case_id", "") or "")
        if run_case_id and person_case_id != run_case_id:
            return {
                "ok": False,
                "error": "The selected person belongs to a different investigation.",
            }

        service = PersonMentionSelectionService(
            source_service=source_service,
            evidence_service=evidence_service,
            evidence_link_service=link_service,
        )
        try:
            result = service.add(person=person, mention=payload)
            if result.duplicate:
                return {
                    "ok": True,
                    "duplicate": True,
                    "message": "This mention is already attached to the person.",
                    "evidenceId": result.evidence_id,
                }
            self._container.commit()
        except Exception as exc:
            try:
                self._container.rollback()
            except Exception:
                LOGGER.debug("Rollback after mention selection failed", exc_info=True)
            LOGGER.exception("Unable to attach corroborating mention to PERSON")
            return {"ok": False, "error": str(exc)}

        self._set_message("Corroborating mention added to person profile.")
        return {
            "ok": True,
            "duplicate": False,
            "message": "Corroborating mention added to person profile.",
            "evidenceId": result.evidence_id,
        }

    def _set_message(self, value: str) -> None:
        normalized = str(value or "")
        if normalized != self._message:
            self._message = normalized
            self.messageChanged.emit()

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
