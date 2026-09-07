"""
M021.5 — Controlled Recursive OSINT Pivot Expansion.

Breadth-first recursive enrichment over persisted Entity pivots.

The service reuses:
- OsintEnrichmentService
- PivotTraversalState
- PivotPolicyLimits
- M021.1 visited-pivot guards

It does not bypass connector policy and does not inspect raw finding text.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
    OsintTargetEnrichmentResult,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_candidates import (
    OsintPivotCandidatePolicy,
    RecursivePivotCandidate,
)
from app.osint.pivot_policy import PivotTraversalState


class RecursiveExpansionStopReason(str, Enum):
    QUEUE_EXHAUSTED = "queue_exhausted"
    MAX_DEPTH_REACHED = "max_depth_reached"
    NEW_ENTITY_BUDGET_REACHED = "new_entity_budget_reached"


@dataclass(frozen=True, slots=True)
class RecursiveEnrichmentSeed:
    target_type: OsintTargetType
    value: str
    parent_entity_id: UUID | None = None


@dataclass(slots=True)
class RecursiveEnrichmentResult:
    case_id: UUID
    state: PivotTraversalState
    runs: list[OsintTargetEnrichmentResult] = field(
        default_factory=list
    )
    candidates_discovered: int = 0
    candidates_enqueued: int = 0
    candidates_deduplicated: int = 0
    candidates_unsupported: int = 0
    stop_reason: RecursiveExpansionStopReason = (
        RecursiveExpansionStopReason.QUEUE_EXHAUSTED
    )

    @property
    def targets_processed(self) -> int:
        return len(self.runs)

    @property
    def persisted_findings(self) -> int:
        return sum(
            item.persisted_findings
            for item in self.runs
        )

    @property
    def sources_created(self) -> int:
        return sum(
            item.sources_created
            for item in self.runs
        )

    @property
    def evidences_created(self) -> int:
        return sum(
            item.evidences_created
            for item in self.runs
        )

    @property
    def entities_created(self) -> int:
        return sum(
            item.entities_created
            for item in self.runs
        )


class OsintRecursiveEnrichmentService:
    """
    Run bounded breadth-first automatic OSINT enrichment.

    Root seeds are processed at depth=0.
    Entities discovered from a depth=N run are queued for depth=N+1.
    """

    def __init__(
        self,
        *,
        enrichment_service: OsintEnrichmentService,
        candidate_policy: OsintPivotCandidatePolicy | None = None,
    ) -> None:
        self.enrichment_service = enrichment_service
        self.candidate_policy = (
            candidate_policy
            or OsintPivotCandidatePolicy()
        )

    def enrich(
        self,
        *,
        case_id: UUID,
        seeds: tuple[RecursiveEnrichmentSeed, ...],
        state: PivotTraversalState | None = None,
        seed_depth: int = 0,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> RecursiveEnrichmentResult:
        if seed_depth < 0:
            raise ValueError("seed_depth must be >= 0.")

        traversal_state = state or PivotTraversalState()
        result = RecursiveEnrichmentResult(
            case_id=case_id,
            state=traversal_state,
        )

        queue: deque[
            tuple[
                OsintTargetType,
                str,
                UUID | None,
                int,
            ]
        ] = deque()

        scheduled: set[
            tuple[
                OsintTargetType,
                str,
                UUID | None,
            ]
        ] = set()

        for seed in seeds:
            value = seed.value.strip()
            if not value:
                continue

            key = self._schedule_key(
                seed.target_type,
                value,
                seed.parent_entity_id,
            )
            if key in scheduled:
                result.candidates_deduplicated += 1
                continue

            scheduled.add(key)
            queue.append(
                (
                    seed.target_type,
                    value,
                    seed.parent_entity_id,
                    seed_depth,
                )
            )

        limits = (
            self.enrichment_service
            .execution_service
            .router
            .policy
            .limits
        )

        while queue:
            target_type, value, entity_id, depth = (
                queue.popleft()
            )

            if depth > limits.max_depth:
                result.stop_reason = (
                    RecursiveExpansionStopReason
                    .MAX_DEPTH_REACHED
                )
                continue

            if (
                traversal_state.new_entities_count
                >= limits.max_new_entities
            ):
                result.stop_reason = (
                    RecursiveExpansionStopReason
                    .NEW_ENTITY_BUDGET_REACHED
                )
                break

            run = self.enrichment_service.enrich_target(
                case_id=case_id,
                target_type=target_type,
                value=value,
                parent_entity_id=entity_id,
                depth=depth,
                state=traversal_state,
                timeout=timeout,
                use_cache=use_cache,
                save_raw_output=save_raw_output,
                include_metadata=include_metadata,
                include_related=include_related,
            )
            result.runs.append(run)

            next_depth = depth + 1
            candidates = (
                self.candidate_policy
                .from_enrichment_result(
                    run,
                    next_depth=next_depth,
                )
            )
            result.candidates_discovered += len(
                candidates
            )

            if next_depth > limits.max_depth:
                if candidates:
                    result.stop_reason = (
                        RecursiveExpansionStopReason
                        .MAX_DEPTH_REACHED
                    )
                continue

            for candidate in candidates:
                if (
                    traversal_state.new_entities_count
                    >= limits.max_new_entities
                ):
                    result.stop_reason = (
                        RecursiveExpansionStopReason
                        .NEW_ENTITY_BUDGET_REACHED
                    )
                    break

                key = self._schedule_key(
                    candidate.target_type,
                    candidate.value,
                    candidate.entity_id,
                )
                if key in scheduled:
                    result.candidates_deduplicated += 1
                    continue

                scheduled.add(key)
                queue.append(
                    (
                        candidate.target_type,
                        candidate.value,
                        candidate.entity_id,
                        candidate.depth,
                    )
                )
                result.candidates_enqueued += 1

            if (
                result.stop_reason
                is RecursiveExpansionStopReason
                .NEW_ENTITY_BUDGET_REACHED
            ):
                break

        return result

    @staticmethod
    def _schedule_key(
        target_type: OsintTargetType,
        value: str,
        entity_id: UUID | None,
    ) -> tuple[
        OsintTargetType,
        str,
        UUID | None,
    ]:
        return (
            target_type,
            value.strip().casefold(),
            entity_id,
        )
