"""
M021.4 — Policy-controlled OSINT Enrichment Application Service.

One production entry point for Investigation Engine OSINT enrichment:

    target/entity
      -> M021 Pivot Policy + Capability Router
      -> M021 Execution Boundary
      -> existing OsintPipeline
      -> M021 Findings Persistence
      -> Source / Evidence / Entity

This service does not perform recursive expansion yet.
It also does not commit the SQLAlchemy transaction; transaction ownership
remains with the caller/application boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.osint.enrichment_execution import (
    EnrichmentExecutionResult,
    EnrichmentExecutionStatus,
    OsintEnrichmentExecutionService,
)
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
    OsintPersistenceResult,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


@dataclass(slots=True)
class OsintTargetEnrichmentResult:
    case_id: UUID
    target_type: OsintTargetType
    target_value: str
    parent_entity_id: UUID | None
    depth: int
    state: PivotTraversalState
    executions: list[EnrichmentExecutionResult] = field(default_factory=list)
    persistence: list[OsintPersistenceResult] = field(default_factory=list)

    @property
    def goals_attempted(self) -> int:
        return len(self.executions)

    @property
    def persisted_findings(self) -> int:
        return sum(item.persisted_findings for item in self.persistence)

    @property
    def sources_created(self) -> int:
        return sum(item.sources_created for item in self.persistence)

    @property
    def evidences_created(self) -> int:
        return sum(item.evidences_created for item in self.persistence)

    @property
    def entities_created(self) -> int:
        return sum(item.entities_created for item in self.persistence)

    @property
    def links_created(self) -> int:
        return sum(item.links_created for item in self.persistence)

    @property
    def successful_goals(self) -> int:
        return sum(
            item.status is EnrichmentExecutionStatus.SUCCESS
            for item in self.executions
        )

    @property
    def partial_goals(self) -> int:
        return sum(
            item.status is EnrichmentExecutionStatus.PARTIAL
            for item in self.executions
        )

    @property
    def failed_goals(self) -> int:
        return sum(
            item.status is EnrichmentExecutionStatus.FAILED
            for item in self.executions
        )

    @property
    def skipped_goals(self) -> int:
        return sum(
            item.status is EnrichmentExecutionStatus.SKIPPED
            for item in self.executions
        )


class OsintEnrichmentService:
    """
    Application-level orchestration for one target enrichment pass.

    The service intentionally performs no recursive discovery. New entities
    created during persistence are counted in PivotTraversalState so M021.5
    can later enforce recursion budgets using the same state object.
    """

    def __init__(
        self,
        *,
        execution_service: OsintEnrichmentExecutionService,
        persistence_service: OsintFindingPersistenceService,
    ) -> None:
        self.execution_service = execution_service
        self.persistence_service = persistence_service

    def enrich_target(
        self,
        *,
        case_id: UUID,
        target_type: OsintTargetType,
        value: str,
        parent_entity_id: UUID | None = None,
        depth: int = 0,
        state: PivotTraversalState | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
        new_entity_limit: int | None = None,
    ) -> OsintTargetEnrichmentResult:
        """
        Execute and persist every automatic default goal for one target.

        No transaction commit is performed here.
        """
        traversal_state = state or PivotTraversalState()

        executions = list(
            self.execution_service.execute_defaults(
                target_type=target_type,
                value=value,
                depth=depth,
                entity_identity=self._entity_identity(
                    parent_entity_id=parent_entity_id,
                    target_type=target_type,
                    value=value,
                ),
                state=traversal_state,
                case_id=str(case_id),
                timeout=timeout,
                use_cache=use_cache,
                save_raw_output=save_raw_output,
                include_metadata=include_metadata,
                include_related=include_related,
                entity_budget_limit=new_entity_limit,
            )
        )

        persistence_results: list[OsintPersistenceResult] = []

        for execution in executions:
            # Persistence service itself ignores FAILED/NOT_AVAILABLE records,
            # but we still call it for SUCCESS/PARTIAL aggregate executions so
            # usable findings from a partially successful route are retained.
            if execution.status not in {
                EnrichmentExecutionStatus.SUCCESS,
                EnrichmentExecutionStatus.PARTIAL,
            }:
                continue

            persisted = self.persistence_service.persist_execution(
                case_id=case_id,
                target_type=target_type,
                target_value=value,
                goal=execution.route.goal,
                execution=execution,
                parent_entity_id=parent_entity_id,
            )
            persistence_results.append(persisted)

            if persisted.entities_created:
                traversal_state.add_new_entities(
                    persisted.entities_created
                )

        return OsintTargetEnrichmentResult(
            case_id=case_id,
            target_type=target_type,
            target_value=value,
            parent_entity_id=parent_entity_id,
            depth=depth,
            state=traversal_state,
            executions=executions,
            persistence=persistence_results,
        )

    @staticmethod
    def _entity_identity(
        *,
        parent_entity_id: UUID | None,
        target_type: OsintTargetType,
        value: str,
    ) -> str:
        if parent_entity_id is not None:
            return f"entity:{parent_entity_id}"

        return (
            "target:"
            f"{target_type.value}:"
            f"{value.strip().casefold()}"
        )
