"""
Entity resolution pipeline.

Coordinates high-level entity resolution workflow.

Responsibilities:

- resolve one explicitly selected entity pair
- generate and resolve candidate pairs for entity batches
- resolve already prepared candidates
- optionally integrate explicit Evidence identity observations
- expose explicit merge action
- keep analysis and persistence separated

Does NOT:

- automatically merge MATCH results
- modify Entity objects during resolution
- query an entire case by itself
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
)

from app.entity_resolution.candidate_generator import (
    EntityCandidateGenerator,
    EntityResolutionCandidate,
)

from app.entity_resolution.contracts import (
    EntityResolutionResult,
)

from app.entity_resolution.evidence_bridge import (
    EvidenceIdentityBridgeObservation,
)

from app.models.entity import (
    Entity,
)

from app.models.entity_merge import (
    EntityMerge,
)

from app.services.entity_resolver_service import (
    EntityResolverService,
)


class EntityResolutionPipeline:
    """
    High-level entity resolution workflow.

    Pipeline:

        Entities
            ↓
        Candidate Generator
            ↓
        EntityResolverService
            ↓
        Batch Resolution Engine
            ↓
        EntityResolutionResult

    Optional Evidence identity observations enter the
    same resolution signal pipeline before scoring.

    Persistence is a separate explicit action.
    """

    def __init__(
        self,
        session: Session,
        *,
        resolver: (
            EntityResolverService
            | None
        ) = None,
        candidate_generator: (
            EntityCandidateGenerator
            | None
        ) = None,
    ) -> None:

        self.session = session

        self.resolver = (
            resolver
            or EntityResolverService(
                session
            )
        )

        self.candidate_generator = (
            candidate_generator
            or EntityCandidateGenerator()
        )

    # ==========================================================
    # Single pair
    # ==========================================================

    def process_pair(
        self,
        first: Entity,
        second: Entity,
        *,
        evidence_observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None = None,
    ) -> EntityResolutionResult:
        """
        Resolve one explicitly selected pair.

        Optional Evidence observations are integrated
        only when explicitly provided.

        No database write is performed.
        """

        return (
            self.resolver
            .resolve_pair(
                first,
                second,
                evidence_observations=(
                    evidence_observations
                ),
            )
        )

    # ==========================================================
    # Entity batch
    # ==========================================================

    def process_entities(
        self,
        entities: Iterable[
            Entity
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
        Generate candidate pairs from entities and run
        them through the complete resolution engine.

        Evidence observations may be supplied for
        selected generated pairs.

        This is the main batch entry point.
        """

        candidates = (
            self.generate_candidates(
                entities
            )
        )

        return (
            self.process_candidates(
                candidates,
                evidence_observations_by_pair=(
                    evidence_observations_by_pair
                ),
            )
        )

    # ==========================================================
    # Candidate generation
    # ==========================================================

    def generate_candidates(
        self,
        entities: Iterable[
            Entity
        ],
    ) -> list[
        EntityResolutionCandidate
    ]:
        """
        Generate conservative resolution candidates.
        """

        return (
            self.candidate_generator
            .generate(
                entities
            )
        )

    # ==========================================================
    # Prepared candidates
    # ==========================================================

    def process_candidates(
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
        Resolve already prepared candidates.

        Evidence observations are optional and must be
        explicitly mapped to entity pairs.
        """

        return (
            self.resolver
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
        Return True only when modern policy
        classifies the pair as MATCH.

        Optional Evidence observations participate
        only when explicitly provided.

        No merge is performed.
        """

        return (
            self.resolver
            .are_same_entity(
                first,
                second,
                evidence_observations=(
                    evidence_observations
                ),
            )
        )

    # ==========================================================
    # Explicit persistence
    # ==========================================================

    def merge_pair(
        self,
        source: Entity,
        target: Entity,
        resolution: EntityResolutionResult,
        *,
        reason: str | None = None,
    ) -> EntityMerge:
        """
        Explicitly persist an approved MATCH.

        Resolution and merge remain separate operations.
        """

        return (
            self.resolver
            .merge_resolved_pair(
                source,
                target,
                resolution,
                reason=reason,
            )
        )
