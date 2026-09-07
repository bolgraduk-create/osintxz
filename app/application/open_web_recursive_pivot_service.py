"""M021.14 Open-Web persisted entities -> existing controlled recursion."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.open_web_enrichment_service import OpenWebEnrichmentResult
from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentResult,
    RecursiveEnrichmentSeed,
)
from app.osint.pivot_candidates import (
    OsintPivotCandidatePolicy,
    RecursivePivotCandidate,
)
from app.osint.pivot_policy import PivotTraversalState


@dataclass(slots=True)
class OpenWebRecursivePivotResult:
    open_web_result: OpenWebEnrichmentResult
    candidates: tuple[RecursivePivotCandidate, ...] = field(default_factory=tuple)
    recursion: RecursiveEnrichmentResult | None = None

    @property
    def candidates_discovered(self) -> int:
        return len(self.candidates)

    @property
    def recursive_targets_processed(self) -> int:
        return 0 if self.recursion is None else self.recursion.targets_processed


class OpenWebRecursivePivotService:
    """Bridge persisted Open-Web entities into the existing M021.5 BFS."""

    def __init__(
        self,
        *,
        recursive_service: OsintRecursiveEnrichmentService,
        candidate_policy: OsintPivotCandidatePolicy | None = None,
    ) -> None:
        self.recursive_service = recursive_service
        self.candidate_policy = candidate_policy or OsintPivotCandidatePolicy()

    def expand(
        self,
        *,
        case_id: UUID,
        open_web_result: OpenWebEnrichmentResult,
        state: PivotTraversalState | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> OpenWebRecursivePivotResult:
        next_depth = int(open_web_result.query.depth) + 1

        candidates = self.candidate_policy.from_persistence_results(
            open_web_result.persistence,
            next_depth=next_depth,
            discovered_from_entity_id=open_web_result.query.parent_entity_id,
        )

        if not candidates:
            return OpenWebRecursivePivotResult(
                open_web_result=open_web_result,
                candidates=(),
                recursion=None,
            )

        seeds = tuple(
            RecursiveEnrichmentSeed(
                target_type=candidate.target_type,
                value=candidate.value,
                parent_entity_id=candidate.entity_id,
            )
            for candidate in candidates
        )

        recursion = self.recursive_service.enrich(
            case_id=case_id,
            seeds=seeds,
            state=state,
            seed_depth=next_depth,
            timeout=timeout,
            use_cache=use_cache,
            save_raw_output=save_raw_output,
            include_metadata=include_metadata,
            include_related=include_related,
        )

        return OpenWebRecursivePivotResult(
            open_web_result=open_web_result,
            candidates=candidates,
            recursion=recursion,
        )
