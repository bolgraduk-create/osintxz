"""Thread-owned OSINT collection worker for the QML desktop interface.

The worker creates a fresh SQLAlchemy session and a fresh canonical
ServiceContainer inside the worker thread. No ORM object is emitted back to the
GUI thread; completed enrichment data is converted to plain Python structures
before the worker-owned session is committed/closed.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.osint.models import OsintTargetType


class OsintCollectionWorker(QObject):
    """Execute one persisted OSINT enrichment pass outside the GUI thread."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        case_id: str,
        target_type: str,
        value: str,
        timeout: int = 30,
        use_cache: bool = True,
    ) -> None:
        super().__init__()
        self.case_id = str(case_id)
        self.target_type = str(target_type)
        self.value = str(value)
        self.timeout = int(timeout)
        self.use_cache = bool(use_cache)

    @Slot()
    def run(self) -> None:
        """Create a thread-local application boundary, execute, persist, close."""
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            session = create_session()
            container = ServiceContainer(session)
            enrichment = (
                container.investigation_target_enrichment_service.enrich(
                    case_id=UUID(self.case_id),
                    target_type=OsintTargetType(self.target_type),
                    value=self.value,
                    timeout=self.timeout,
                    use_cache=self.use_cache,
                )
            )

            # Build a transport-only snapshot while every ORM instance still
            # belongs to this thread/session. Nothing session-bound crosses the
            # Qt thread boundary.
            snapshot = self._snapshot_enrichment(enrichment)
            container.commit()

            self.succeeded.emit(
                {
                    "snapshot": snapshot,
                    "duration": perf_counter() - started,
                }
            )
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass

            self.failed.emit(
                {
                    "error": str(exc),
                    "duration": perf_counter() - started,
                }
            )
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass

    @classmethod
    def _snapshot_enrichment(cls, enrichment: Any) -> dict[str, Any]:
        executions: list[dict[str, Any]] = []

        for execution in list(getattr(enrichment, "executions", ()) or ()):
            route = getattr(execution, "route", None)
            goal_object = getattr(route, "goal", None)
            goal = getattr(goal_object, "value", None) or str(goal_object or "")
            status_object = getattr(execution, "status", None)
            execution_status = (
                getattr(status_object, "value", None)
                or str(status_object or "unknown")
            )

            records: list[dict[str, Any]] = []
            for record in list(getattr(execution, "records", ()) or ()):
                result = getattr(record, "result", None)
                capability = getattr(record, "capability", None)
                if result is None:
                    continue

                result_status_object = getattr(result, "status", None)
                result_status = (
                    getattr(result_status_object, "value", None)
                    or str(result_status_object or "unknown")
                )

                findings = [
                    cls._snapshot_finding(finding)
                    for finding in list(getattr(result, "findings", ()) or ())
                ]

                records.append(
                    {
                        "runtimeConnectorName": getattr(
                            record,
                            "runtime_connector_name",
                            None,
                        ),
                        "connector": getattr(result, "connector", None),
                        "capabilityDisplayName": getattr(
                            capability,
                            "display_name",
                            None,
                        ),
                        "capabilityModule": getattr(
                            capability,
                            "module",
                            None,
                        ),
                        "status": result_status,
                        "error": getattr(result, "error", None),
                        "executionTime": cls._safe_float(
                            getattr(result, "execution_time", 0.0)
                        ),
                        "findings": findings,
                    }
                )

            executions.append(
                {
                    "goal": goal,
                    "status": execution_status,
                    "error": getattr(execution, "error", None),
                    "records": records,
                }
            )

        persistences: list[dict[str, Any]] = []
        raw_persistences = list(
            getattr(enrichment, "persistences", ())
            or getattr(enrichment, "persistence", ())
            or ()
        )
        for persistence in raw_persistences:
            persisted_rows: list[dict[str, Any]] = []
            for persisted in list(getattr(persistence, "persisted", ()) or ()):
                evidence = getattr(persisted, "evidence", None)
                evidence_snapshot = None
                if evidence is not None:
                    evidence_type = getattr(evidence, "evidence_type", None)
                    evidence_snapshot = {
                        "id": str(getattr(evidence, "id", "") or ""),
                        "title": getattr(evidence, "title", None),
                        "value": getattr(evidence, "value", None),
                        "type": (
                            getattr(evidence_type, "value", None)
                            or str(evidence_type or "evidence")
                        ),
                    }

                entities = []
                for entity in list(getattr(persisted, "entities", ()) or ()):
                    entity_type = getattr(entity, "entity_type", None)
                    entities.append(
                        {
                            "id": str(getattr(entity, "id", "") or ""),
                            "value": getattr(entity, "value", None),
                            "type": (
                                getattr(entity_type, "value", None)
                                or str(entity_type or "entity")
                            ),
                            "confidence": cls._safe_optional_float(
                                getattr(entity, "confidence", None)
                            ),
                        }
                    )

                persisted_rows.append(
                    {
                        "evidence": evidence_snapshot,
                        "entities": entities,
                    }
                )

            persistences.append({"persisted": persisted_rows})

        return {
            "executions": executions,
            "persistences": persistences,
            "counts": {
                "persistedFindings": int(
                    getattr(enrichment, "persisted_findings", 0) or 0
                ),
                "sourcesCreated": int(
                    getattr(enrichment, "sources_created", 0) or 0
                ),
                "evidenceCreated": int(
                    getattr(enrichment, "evidences_created", 0) or 0
                ),
                "entitiesCreated": int(
                    getattr(enrichment, "entities_created", 0) or 0
                ),
                "linksCreated": int(
                    getattr(enrichment, "links_created", 0) or 0
                ),
            },
        }

    @staticmethod
    def _snapshot_finding(finding: Any) -> dict[str, Any]:
        metadata = getattr(finding, "metadata", None)
        return {
            "category": getattr(finding, "category", None),
            "value": getattr(finding, "value", None),
            "confidence": OsintCollectionWorker._safe_optional_float(
                getattr(finding, "confidence", None)
            ),
            "source": getattr(finding, "source", None),
            "url": getattr(finding, "url", None),
            "reliability": OsintCollectionWorker._safe_optional_float(
                getattr(finding, "reliability", None)
            ),
            "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        }

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
