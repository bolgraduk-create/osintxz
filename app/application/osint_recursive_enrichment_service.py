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
from time import monotonic
from typing import Callable
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
    MAX_TARGETS_REACHED = "max_targets_reached"
    TIME_BUDGET_REACHED = "time_budget_reached"


@dataclass(frozen=True, slots=True)
class RecursiveEnrichmentSeed:
    target_type: OsintTargetType
    value: str
    parent_entity_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RecursiveEnrichmentProgress:
    """Progress snapshot emitted between recursive targets.

    The callback is intentionally target-level rather than connector-level:
    connectors keep their own timeout contract, while the application/UI can
    still show that the BFS is alive and which persisted pivot is being worked.
    """

    phase: str
    target_type: OsintTargetType | None = None
    value: str | None = None
    depth: int | None = None
    targets_processed: int = 0
    queued_targets: int = 0
    candidates_discovered: int = 0
    candidates_enqueued: int = 0
    new_entities_count: int = 0
    persisted_findings: int = 0
    entities_created: int = 0
    elapsed_seconds: float = 0.0
    stop_reason: RecursiveExpansionStopReason | None = None


RecursiveProgressCallback = Callable[
    [RecursiveEnrichmentProgress],
    None,
]


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
        progress_callback: RecursiveProgressCallback | None = None,
        max_targets: int | None = None,
        time_budget_seconds: float | None = None,
        per_target_new_entity_limit: int | None = None,
    ) -> RecursiveEnrichmentResult:
        if seed_depth < 0:
            raise ValueError("seed_depth must be >= 0.")
        if max_targets is not None and max_targets <= 0:
            raise ValueError("max_targets must be > 0 when provided.")
        if (
            time_budget_seconds is not None
            and time_budget_seconds <= 0
        ):
            raise ValueError(
                "time_budget_seconds must be > 0 when provided."
            )
        if (
            per_target_new_entity_limit is not None
            and per_target_new_entity_limit <= 0
        ):
            raise ValueError(
                "per_target_new_entity_limit must be > 0 when provided."
            )

        started_at = monotonic()
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

        self._notify_progress(
            progress_callback,
            RecursiveEnrichmentProgress(
                phase="queue_seeded",
                targets_processed=0,
                queued_targets=len(queue),
                candidates_discovered=0,
                candidates_enqueued=0,
                new_entities_count=(
                    traversal_state.new_entities_count
                ),
                elapsed_seconds=(
                    monotonic() - started_at
                ),
            ),
        )

        while queue:
            if (
                max_targets is not None
                and result.targets_processed >= max_targets
            ):
                result.stop_reason = (
                    RecursiveExpansionStopReason
                    .MAX_TARGETS_REACHED
                )
                self._notify_progress(
                    progress_callback,
                    RecursiveEnrichmentProgress(
                        phase="stopped",
                        targets_processed=result.targets_processed,
                        queued_targets=len(queue),
                        candidates_discovered=(
                            result.candidates_discovered
                        ),
                        candidates_enqueued=(
                            result.candidates_enqueued
                        ),
                        new_entities_count=(
                            traversal_state.new_entities_count
                        ),
                        elapsed_seconds=(
                            monotonic() - started_at
                        ),
                        stop_reason=result.stop_reason,
                    ),
                )
                break

            if (
                time_budget_seconds is not None
                and (
                    monotonic() - started_at
                ) >= time_budget_seconds
            ):
                result.stop_reason = (
                    RecursiveExpansionStopReason
                    .TIME_BUDGET_REACHED
                )
                self._notify_progress(
                    progress_callback,
                    RecursiveEnrichmentProgress(
                        phase="stopped",
                        targets_processed=result.targets_processed,
                        queued_targets=len(queue),
                        candidates_discovered=(
                            result.candidates_discovered
                        ),
                        candidates_enqueued=(
                            result.candidates_enqueued
                        ),
                        new_entities_count=(
                            traversal_state.new_entities_count
                        ),
                        elapsed_seconds=(
                            monotonic() - started_at
                        ),
                        stop_reason=result.stop_reason,
                    ),
                )
                break

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

            self._notify_progress(
                progress_callback,
                RecursiveEnrichmentProgress(
                    phase="target_started",
                    target_type=target_type,
                    value=value,
                    depth=depth,
                    targets_processed=result.targets_processed,
                    queued_targets=len(queue),
                    candidates_discovered=(
                        result.candidates_discovered
                    ),
                    candidates_enqueued=(
                        result.candidates_enqueued
                    ),
                    new_entities_count=(
                        traversal_state.new_entities_count
                    ),
                    elapsed_seconds=(
                        monotonic() - started_at
                    ),
                ),
            )

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
                new_entity_limit=per_target_new_entity_limit,
            )
            result.runs.append(run)

            self._notify_progress(
                progress_callback,
                RecursiveEnrichmentProgress(
                    phase="target_finished",
                    target_type=target_type,
                    value=value,
                    depth=depth,
                    targets_processed=result.targets_processed,
                    queued_targets=len(queue),
                    candidates_discovered=(
                        result.candidates_discovered
                    ),
                    candidates_enqueued=(
                        result.candidates_enqueued
                    ),
                    new_entities_count=(
                        traversal_state.new_entities_count
                    ),
                    persisted_findings=(
                        run.persisted_findings
                    ),
                    entities_created=(
                        run.entities_created
                    ),
                    elapsed_seconds=(
                        monotonic() - started_at
                    ),
                ),
            )

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

        if (
            result.stop_reason
            is RecursiveExpansionStopReason.QUEUE_EXHAUSTED
        ):
            self._notify_progress(
                progress_callback,
                RecursiveEnrichmentProgress(
                    phase="completed",
                    targets_processed=result.targets_processed,
                    queued_targets=0,
                    candidates_discovered=(
                        result.candidates_discovered
                    ),
                    candidates_enqueued=(
                        result.candidates_enqueued
                    ),
                    new_entities_count=(
                        traversal_state.new_entities_count
                    ),
                    elapsed_seconds=(
                        monotonic() - started_at
                    ),
                    stop_reason=result.stop_reason,
                ),
            )

        return result

    @staticmethod
    def _notify_progress(
        callback: RecursiveProgressCallback | None,
        progress: RecursiveEnrichmentProgress,
    ) -> None:
        if callback is None:
            return

        try:
            callback(progress)
        except Exception:
            # UI/reporting progress must never break evidence collection.
            return

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
