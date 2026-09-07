from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


@dataclass(slots=True)
class InvestigationTargetEnrichmentSummary:
    target_type: OsintTargetType
    target_value: str
    executions: tuple[object, ...] = field(default_factory=tuple)
    persistences: tuple[object, ...] = field(default_factory=tuple)

    @property
    def connector_records(self) -> tuple[object, ...]:
        rows = []
        for execution in self.executions:
            rows.extend(getattr(execution, "records", ()) or ())
        return tuple(rows)

    @property
    def findings_total(self) -> int:
        total = 0
        for record in self.connector_records:
            result = getattr(record, "result", None)
            total += len(getattr(result, "findings", ()) or ())
        return total

    @property
    def persisted_findings(self) -> int:
        return sum(int(getattr(x, "persisted_findings", 0) or 0) for x in self.persistences)

    @property
    def sources_created(self) -> int:
        return sum(int(getattr(x, "sources_created", 0) or 0) for x in self.persistences)

    @property
    def evidences_created(self) -> int:
        return sum(int(getattr(x, "evidences_created", 0) or 0) for x in self.persistences)

    @property
    def entities_created(self) -> int:
        return sum(int(getattr(x, "entities_created", 0) or 0) for x in self.persistences)

    @property
    def links_created(self) -> int:
        return sum(int(getattr(x, "links_created", 0) or 0) for x in self.persistences)

    @property
    def provider_rows(self) -> tuple[dict, ...]:
        rows = []
        for execution in self.executions:
            goal = getattr(getattr(execution, "route", None), "goal", None)
            for record in getattr(execution, "records", ()) or ():
                result = getattr(record, "result", None)
                capability = getattr(record, "capability", None)
                status = getattr(result, "status", None)
                if hasattr(status, "value"):
                    status = status.value
                rows.append({
                    "provider": (
                        getattr(record, "runtime_connector_name", None)
                        or getattr(result, "connector", None)
                        or getattr(capability, "display_name", None)
                        or getattr(capability, "module", None)
                        or "unknown"
                    ),
                    "goal": getattr(goal, "value", None) or str(goal or ""),
                    "status": status or "unknown",
                    "findings": len(getattr(result, "findings", ()) or ()),
                    "error": getattr(result, "error", None),
                })
        return tuple(rows)


class InvestigationTargetEnrichmentService:
    def __init__(self, *, execution_service, persistence_service) -> None:
        self.execution_service = execution_service
        self.persistence_service = persistence_service

    def enrich(
        self,
        *,
        case_id: UUID,
        target_type: OsintTargetType,
        value: str,
        timeout: int = 300,
        use_cache: bool = True,
    ) -> InvestigationTargetEnrichmentSummary:
        state = PivotTraversalState()

        executions = self.execution_service.execute_defaults(
            target_type=target_type,
            value=value,
            depth=0,
            entity_identity=f"ui:{case_id}:{target_type.value}:{value}",
            state=state,
            case_id=str(case_id),
            timeout=timeout,
            use_cache=use_cache,
            save_raw_output=False,
            include_metadata=True,
            include_related=True,
        )

        persistences = []

        for execution in executions:
            goal = getattr(getattr(execution, "route", None), "goal", None)
            if goal is None:
                continue

            persistence = self.persistence_service.persist_execution(
                case_id=case_id,
                target_type=target_type,
                target_value=value,
                goal=goal,
                execution=execution,
            )
            persistences.append(persistence)

        return InvestigationTargetEnrichmentSummary(
            target_type=target_type,
            target_value=value,
            executions=tuple(executions),
            persistences=tuple(persistences),
        )
