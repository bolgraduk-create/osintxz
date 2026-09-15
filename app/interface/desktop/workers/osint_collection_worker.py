"""Thread-owned recursive OSINT collection worker for the QML desktop interface.

The worker creates a fresh SQLAlchemy session and a fresh canonical
ServiceContainer inside the worker thread. The production path uses the
bounded M021 recursive-enrichment service so persisted Entity pivots can be
processed without moving ORM objects across the Qt thread boundary.

Only plain Python transport snapshots and progress dictionaries are emitted
back to the GUI thread.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.osint.models import OsintTargetType


class OsintCollectionWorker(QObject):
    """Execute one bounded, persisted recursive OSINT enrichment run."""

    # Conservative UI-boundary limits. Core pivot policy still owns max depth,
    # per-entity pivot budgets and the global new-entity budget.
    RECURSIVE_MAX_TARGETS = 24
    RECURSIVE_TIME_BUDGET_SECONDS = 180.0
    RECURSIVE_PER_TARGET_NEW_ENTITY_LIMIT = 12

    progress = Signal(object)
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
        """Create a thread-local boundary, execute recursive OSINT, persist, close."""
        from app.application.osint_recursive_enrichment_service import (
            RecursiveEnrichmentSeed,
        )
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            session = create_session()
            container = ServiceContainer(session)
            target_type = OsintTargetType(self.target_type)

            enrichment = container.osint_recursive_enrichment_service.enrich(
                case_id=UUID(self.case_id),
                seeds=(
                    RecursiveEnrichmentSeed(
                        target_type=target_type,
                        value=self.value,
                    ),
                ),
                timeout=self.timeout,
                use_cache=self.use_cache,
                save_raw_output=False,
                include_metadata=True,
                include_related=True,
                progress_callback=self._emit_progress,
                max_targets=self.RECURSIVE_MAX_TARGETS,
                time_budget_seconds=self.RECURSIVE_TIME_BUDGET_SECONDS,
                per_target_new_entity_limit=(
                    self.RECURSIVE_PER_TARGET_NEW_ENTITY_LIMIT
                ),
            )

            # Build a transport-only snapshot while every ORM instance still
            # belongs to this thread/session. Nothing session-bound crosses the
            # Qt thread boundary.
            snapshot = self._snapshot_recursive_enrichment(enrichment)
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

    def _emit_progress(self, progress: Any) -> None:
        """Convert recursive-service progress to a Qt-safe plain dictionary."""
        target_type = getattr(progress, "target_type", None)
        stop_reason = getattr(progress, "stop_reason", None)
        self.progress.emit(
            {
                "phase": str(getattr(progress, "phase", "") or ""),
                "targetType": (
                    getattr(target_type, "value", None)
                    or str(target_type or "")
                ),
                "targetValue": str(getattr(progress, "value", "") or ""),
                "depth": self._safe_optional_int(
                    getattr(progress, "depth", None)
                ),
                "targetsProcessed": self._safe_int(
                    getattr(progress, "targets_processed", 0)
                ),
                "queuedTargets": self._safe_int(
                    getattr(progress, "queued_targets", 0)
                ),
                "candidatesDiscovered": self._safe_int(
                    getattr(progress, "candidates_discovered", 0)
                ),
                "candidatesEnqueued": self._safe_int(
                    getattr(progress, "candidates_enqueued", 0)
                ),
                "newEntitiesCount": self._safe_int(
                    getattr(progress, "new_entities_count", 0)
                ),
                "persistedFindings": self._safe_int(
                    getattr(progress, "persisted_findings", 0)
                ),
                "entitiesCreated": self._safe_int(
                    getattr(progress, "entities_created", 0)
                ),
                "elapsedSeconds": self._safe_float(
                    getattr(progress, "elapsed_seconds", 0.0)
                ),
                "stopReason": (
                    getattr(stop_reason, "value", None)
                    or str(stop_reason or "")
                ),
            }
        )

    @classmethod
    def _snapshot_recursive_enrichment(cls, enrichment: Any) -> dict[str, Any]:
        runs = [
            cls._snapshot_target_enrichment(run)
            for run in list(getattr(enrichment, "runs", ()) or ())
        ]

        state = getattr(enrichment, "state", None)
        stop_reason = getattr(enrichment, "stop_reason", None)

        return {
            "runs": runs,
            "counts": {
                "persistedFindings": cls._safe_int(
                    getattr(enrichment, "persisted_findings", 0)
                ),
                "sourcesCreated": cls._safe_int(
                    getattr(enrichment, "sources_created", 0)
                ),
                "evidenceCreated": cls._safe_int(
                    getattr(enrichment, "evidences_created", 0)
                ),
                "entitiesCreated": cls._safe_int(
                    getattr(enrichment, "entities_created", 0)
                ),
                "linksCreated": sum(
                    cls._safe_int(
                        getattr(run, "links_created", 0)
                    )
                    for run in list(getattr(enrichment, "runs", ()) or ())
                ),
            },
            "recursion": {
                "targetsProcessed": len(runs),
                "candidatesDiscovered": cls._safe_int(
                    getattr(enrichment, "candidates_discovered", 0)
                ),
                "candidatesEnqueued": cls._safe_int(
                    getattr(enrichment, "candidates_enqueued", 0)
                ),
                "candidatesDeduplicated": cls._safe_int(
                    getattr(enrichment, "candidates_deduplicated", 0)
                ),
                "candidatesUnsupported": cls._safe_int(
                    getattr(enrichment, "candidates_unsupported", 0)
                ),
                "newEntitiesCount": cls._safe_int(
                    getattr(state, "new_entities_count", 0)
                ),
                "stopReason": (
                    getattr(stop_reason, "value", None)
                    or str(stop_reason or "queue_exhausted")
                ),
                "maxTargets": cls.RECURSIVE_MAX_TARGETS,
                "timeBudgetSeconds": cls.RECURSIVE_TIME_BUDGET_SECONDS,
                "perTargetNewEntityLimit": (
                    cls.RECURSIVE_PER_TARGET_NEW_ENTITY_LIMIT
                ),
            },
        }

    @classmethod
    def _snapshot_target_enrichment(cls, enrichment: Any) -> dict[str, Any]:
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
                            "normalizedValue": getattr(
                                entity,
                                "normalized_value",
                                None,
                            ),
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

        target_type = getattr(enrichment, "target_type", None)
        parent_entity_id = getattr(enrichment, "parent_entity_id", None)
        return {
            "targetType": (
                getattr(target_type, "value", None)
                or str(target_type or "")
            ),
            "targetValue": str(
                getattr(enrichment, "target_value", "") or ""
            ),
            "parentEntityId": (
                str(parent_entity_id) if parent_entity_id is not None else ""
            ),
            "depth": cls._safe_int(getattr(enrichment, "depth", 0)),
            "executions": executions,
            "persistences": persistences,
            "counts": {
                "persistedFindings": cls._safe_int(
                    getattr(enrichment, "persisted_findings", 0)
                ),
                "sourcesCreated": cls._safe_int(
                    getattr(enrichment, "sources_created", 0)
                ),
                "evidenceCreated": cls._safe_int(
                    getattr(enrichment, "evidences_created", 0)
                ),
                "entitiesCreated": cls._safe_int(
                    getattr(enrichment, "entities_created", 0)
                ),
                "linksCreated": cls._safe_int(
                    getattr(enrichment, "links_created", 0)
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

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
