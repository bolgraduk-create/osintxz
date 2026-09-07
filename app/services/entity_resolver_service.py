"""
Entity resolver service.

Coordinates the modern entity-resolution engine
for individual and prepared candidate pairs.

Responsibilities:

- resolve one entity pair non-destructively
- resolve prepared candidate batches
- optionally integrate explicit Evidence identity observations
- expose backward-compatible identity check
- keep resolution decision separate from database merge
- allow merge only as an explicit action after MATCH

Does NOT:

- generate candidates from a whole case
- automatically merge entities during resolution
- silently convert REVIEW into MATCH
- infer identity automatically from shared Evidence
"""

from __future__ import annotations

from collections.abc import (
    Iterable,
    Mapping,
)

from sqlalchemy.orm import Session

from app.entity_resolution.batch_resolution import (
    EntityResolutionBatchResult,
    EntityResolutionBatchService,
)

from app.entity_resolution.candidate_generator import (
    EntityResolutionCandidate,
)

from app.entity_resolution.contracts import (
    EntityResolutionDecision,
    EntityResolutionResult,
)

from app.entity_resolution.evidence_bridge import (
    EvidenceIdentityBridgeObservation,
)

from app.models.entity import Entity

from app.models.entity_merge import (
    EntityMerge,
)

from app.services.entity_merge_service import (
    EntityMergeService,
)


class EntityResolverService:
    """
    High-level non-destructive entity resolver.

    Resolution and persistence are intentionally
    separated:

        resolve(...)
            -> EntityResolutionResult

        merge_resolved_pair(...)
            -> EntityMerge

    Evidence identity observations are optional and
    must always be supplied explicitly.
    """

    def __init__(
        self,
        session: Session,
        *,
        batch_resolution_service: (
            EntityResolutionBatchService
            | None
        ) = None,
        merge_service: (
            EntityMergeService
            | None
        ) = None,
    ) -> None:

        self.session = session

        self.batch_resolution_service = (
            batch_resolution_service
            or EntityResolutionBatchService()
        )

        self.merge_service = (
            merge_service
            or EntityMergeService(
                session
            )
        )

    # ==========================================================
    # Pair resolution
    # ==========================================================

    def resolve(
        self,
        source: Entity,
        target: Entity,
        *,
        evidence_observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None = None,
    ) -> EntityResolutionResult:
        """
        Backward-compatible resolver entry point.

        IMPORTANT:

        Unlike the old implementation, this method
        does NOT create an EntityMerge record.

        Optional Evidence observations are integrated
        only when explicitly provided.

        It returns a complete explainable
        EntityResolutionResult.
        """

        return self.resolve_pair(
            source,
            target,
            evidence_observations=(
                evidence_observations
            ),
        )

    def resolve_pair(
        self,
        first: Entity,
        second: Entity,
        *,
        evidence_observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None = None,
    ) -> EntityResolutionResult:
        """
        Resolve one entity pair non-destructively.

        Old calls without Evidence preserve the
        original Entity Resolution behavior.
        """

        candidate = (
            self._build_direct_candidate(
                first,
                second,
            )
        )

        return (
            self.batch_resolution_service
            .resolve_candidate(
                candidate,
                evidence_observations=(
                    evidence_observations
                ),
            )
        )

    # ==========================================================
    # Prepared candidate batch
    # ==========================================================

    def resolve_candidates(
        self,
        candidates: Iterable[
            EntityResolutionCandidate
        ],
        *,
        evidence_observations_by_pair: (
            Mapping[
                tuple[str, str],
                Iterable[
                    EvidenceIdentityBridgeObservation
                ],
            ]
            | None
        ) = None,
    ) -> EntityResolutionBatchResult:
        """
        Resolve already generated candidate pairs.

        Evidence observations may be supplied for
        selected candidate pairs using canonical
        pair keys.

        No database writes or merges are performed.
        """

        return (
            self.batch_resolution_service
            .resolve_candidates(
                candidates,
                evidence_observations_by_pair=(
                    evidence_observations_by_pair
                ),
            )
        )

    # ==========================================================
    # Backward-compatible identity check
    # ==========================================================

    def are_same_entity(
        self,
        first: Entity,
        second: Entity,
        *,
        evidence_observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None = None,
    ) -> bool:
        """
        Determine whether the modern resolution
        policy classified the pair as MATCH.

        Optional Evidence observations participate
        only when explicitly provided.

        This method remains non-destructive.
        """

        result = self.resolve_pair(
            first,
            second,
            evidence_observations=(
                evidence_observations
            ),
        )

        return (
            result.decision
            ==
            EntityResolutionDecision.MATCH
        )

    # ==========================================================
    # Explicit merge action
    # ==========================================================

    def merge_resolved_pair(
        self,
        source: Entity,
        target: Entity,
        resolution: EntityResolutionResult,
        *,
        reason: str | None = None,
    ) -> EntityMerge:
        """
        Explicitly create an EntityMerge record for
        a pair that has already been resolved as MATCH.

        This is deliberately separate from resolve().
        """

        self._validate_merge_request(
            source=source,
            target=target,
            resolution=resolution,
        )

        merge_reason = (
            reason
            or (
                "approved entity resolution "
                f"match; identity_score="
                f"{resolution.identity_score:.6f}; "
                f"confidence="
                f"{resolution.confidence:.6f}"
            )
        )

        return (
            self.merge_service
            .merge_entities(
                source,
                target,
                reason=merge_reason,
            )
        )

    # ==========================================================
    # Direct candidate
    # ==========================================================

    @staticmethod
    def _build_direct_candidate(
        first: Entity,
        second: Entity,
    ) -> EntityResolutionCandidate:
        """
        Wrap an explicitly requested pair into the
        common candidate contract.

        Candidate generation is not needed because
        the caller already selected this pair.
        """

        entity_type = getattr(
            first,
            "entity_type",
            None,
        )

        type_value = getattr(
            entity_type,
            "value",
            str(
                entity_type
            ),
        )

        return EntityResolutionCandidate(
            first_entity=first,
            second_entity=second,
            reasons=[
                "direct_pair_resolution",
            ],
            blocking_keys=[
                (
                    "direct_pair:"
                    f"{type_value}"
                )
            ],
        )

    # ==========================================================
    # Merge validation
    # ==========================================================

    @staticmethod
    def _validate_merge_request(
        *,
        source: Entity,
        target: Entity,
        resolution: EntityResolutionResult,
    ) -> None:
        """
        Ensure a merge corresponds exactly to an
        approved MATCH result.
        """

        if not isinstance(
            resolution,
            EntityResolutionResult,
        ):

            raise TypeError(
                "resolution must be an "
                "EntityResolutionResult."
            )

        if (
            resolution.decision
            !=
            EntityResolutionDecision.MATCH
        ):

            raise ValueError(
                "Entities may only be merged "
                "after a MATCH resolution."
            )

        source_id = getattr(
            source,
            "id",
            None,
        )

        target_id = getattr(
            target,
            "id",
            None,
        )

        if (
            source_id is None
            or target_id is None
        ):

            raise ValueError(
                "Merge entities require IDs."
            )

        if source_id == target_id:

            raise ValueError(
                "Cannot merge entity into itself."
            )

        expected_ids = {
            str(
                source_id
            ),
            str(
                target_id
            ),
        }

        resolution_ids = {
            str(
                resolution.first_entity_id
            ),
            str(
                resolution.second_entity_id
            ),
        }

        if (
            expected_ids
            !=
            resolution_ids
        ):

            raise ValueError(
                "Resolution result does not "
                "belong to the requested "
                "entity pair."
            )

        source_case_id = getattr(
            source,
            "case_id",
            None,
        )

        target_case_id = getattr(
            target,
            "case_id",
            None,
        )

        if (
            source_case_id is None
            or target_case_id is None
            or source_case_id
            !=
            target_case_id
        ):

            raise ValueError(
                "Cross-case entity merge "
                "is not allowed."
            )

        if (
            getattr(
                source,
                "entity_type",
                None,
            )
            !=
            getattr(
                target,
                "entity_type",
                None,
            )
        ):

            raise ValueError(
                "Entities of different types "
                "cannot be merged."
            )
