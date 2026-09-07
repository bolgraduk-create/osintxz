"""
Batch entity resolution.

Runs already generated entity candidates through the
complete entity-resolution scoring pipeline.

Responsibilities:

- accept EntityResolutionCandidate objects
- deduplicate candidate pairs
- generate exact identifier signals
- generate fuzzy name signals
- calculate positive support
- detect contradictions
- calculate identity score and confidence
- apply decision policy
- build explainable EntityResolutionResult objects
- return deterministic batch statistics

Does NOT:

- generate candidates from the database
- create or update entities
- create EntityMerge records
- perform physical merging
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import (
    Iterable,
    Mapping,
)

from app.entity_resolution.candidate_generator import (
    EntityResolutionCandidate,
)

from app.entity_resolution.contracts import (
    EntityResolutionDecision,
    EntityResolutionResult,
    EntityResolutionSignal,
)

from app.entity_resolution.contradiction_detection import (
    EntityContradictionDetectionService,
)

from app.entity_resolution.exact_identifier_signals import (
    ExactIdentifierSignalBuilder,
)

from app.entity_resolution.evidence_bridge import (
    EvidenceIdentityBridgeObservation,
    EvidenceIdentityBridgeResult,
    EvidenceIdentityBridgeService,
)

from app.entity_resolution.fuzzy_name_signals import (
    FuzzyNameSignalBuilder,
)

from app.entity_resolution.identity_scoring import (
    EntityIdentityScoringService,
)

from app.entity_resolution.resolution_confidence import (
    EntityResolutionConfidenceService,
)

from app.entity_resolution.resolution_explanation import (
    EntityResolutionExplanationService,
)

from app.entity_resolution.resolution_policy import (
    EntityResolutionDecisionPolicy,
)


# ==========================================================
# Batch result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityResolutionBatchResult:
    """
    Result of resolving a batch of candidate pairs.
    """

    results: tuple[
        EntityResolutionResult,
        ...,
    ]

    input_candidate_count: int

    unique_candidate_count: int

    duplicate_candidate_count: int

    match_count: int

    review_count: int

    no_match_count: int

    insufficient_count: int

    @property
    def processed_count(
        self,
    ) -> int:
        """
        Number of unique candidate pairs processed.
        """

        return len(
            self.results
        )

    @property
    def has_matches(
        self,
    ) -> bool:

        return (
            self.match_count
            >
            0
        )

    @property
    def has_reviews(
        self,
    ) -> bool:

        return (
            self.review_count
            >
            0
        )

    @property
    def match_results(
        self,
    ) -> tuple[
        EntityResolutionResult,
        ...,
    ]:

        return tuple(
            result
            for result
            in self.results
            if (
                result.decision
                ==
                EntityResolutionDecision.MATCH
            )
        )

    @property
    def review_results(
        self,
    ) -> tuple[
        EntityResolutionResult,
        ...,
    ]:

        return tuple(
            result
            for result
            in self.results
            if (
                result.decision
                ==
                EntityResolutionDecision.REVIEW
            )
        )

    @property
    def no_match_results(
        self,
    ) -> tuple[
        EntityResolutionResult,
        ...,
    ]:

        return tuple(
            result
            for result
            in self.results
            if (
                result.decision
                ==
                EntityResolutionDecision.NO_MATCH
            )
        )

    @property
    def insufficient_results(
        self,
    ) -> tuple[
        EntityResolutionResult,
        ...,
    ]:

        return tuple(
            result
            for result
            in self.results
            if (
                result.decision
                ==
                EntityResolutionDecision
                .INSUFFICIENT
            )
        )


# ==========================================================
# Batch service
# ==========================================================


class EntityResolutionBatchService:
    """
    Run candidate pairs through the full
    non-destructive resolution pipeline.

    Pipeline:

        Candidate
            ↓
        ExactIdentifierSignalBuilder
            +
        FuzzyNameSignalBuilder
            ↓
        EntityIdentityScoringService
            +
        EntityContradictionDetectionService
            ↓
        EntityResolutionConfidenceService
            ↓
        EntityResolutionDecisionPolicy
            ↓
        EntityResolutionExplanationService
            ↓
        EntityResolutionResult

    No persistence is performed.
    """

    def __init__(
        self,
        *,
        exact_identifier_signal_builder: (
            ExactIdentifierSignalBuilder
            | None
        ) = None,
        fuzzy_name_signal_builder: (
            FuzzyNameSignalBuilder
            | None
        ) = None,
        identity_scoring_service: (
            EntityIdentityScoringService
            | None
        ) = None,
        contradiction_detection_service: (
            EntityContradictionDetectionService
            | None
        ) = None,
        confidence_service: (
            EntityResolutionConfidenceService
            | None
        ) = None,
        decision_policy: (
            EntityResolutionDecisionPolicy
            | None
        ) = None,
        explanation_service: (
            EntityResolutionExplanationService
            | None
        ) = None,
        evidence_bridge_service: (
            EvidenceIdentityBridgeService
            | None
        ) = None,
    ) -> None:

        self.exact_identifier_signal_builder = (
            exact_identifier_signal_builder
            or ExactIdentifierSignalBuilder()
        )

        self.fuzzy_name_signal_builder = (
            fuzzy_name_signal_builder
            or FuzzyNameSignalBuilder()
        )

        self.identity_scoring_service = (
            identity_scoring_service
            or EntityIdentityScoringService()
        )

        self.contradiction_detection_service = (
            contradiction_detection_service
            or EntityContradictionDetectionService()
        )

        self.confidence_service = (
            confidence_service
            or EntityResolutionConfidenceService()
        )

        self.decision_policy = (
            decision_policy
            or EntityResolutionDecisionPolicy()
        )

        self.explanation_service = (
            explanation_service
            or EntityResolutionExplanationService()
        )

        self.evidence_bridge_service = (
            evidence_bridge_service
            or EvidenceIdentityBridgeService()
        )

    # ==========================================================
    # Batch
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
        Resolve all unique candidate pairs.

        Candidate ordering does not affect output ordering.
        Duplicate candidate pairs are merged before scoring.

        Evidence observations are optional and must be
        explicitly bound to a canonical entity-pair key:

            (smaller_entity_id, larger_entity_id)

        Old calls without Evidence remain unchanged.
        """

        candidate_list = list(
            candidates
        )

        input_candidate_count = len(
            candidate_list
        )

        unique_candidates = (
            self._prepare_candidates(
                candidate_list
            )
        )

        duplicate_candidate_count = (
            input_candidate_count
            -
            len(
                unique_candidates
            )
        )

        evidence_map = (
            self._prepare_evidence_observations_by_pair(
                evidence_observations_by_pair
            )
        )

        candidate_keys = {
            self._candidate_pair_key(
                candidate
            )
            for candidate
            in unique_candidates
        }

        unknown_evidence_keys = (
            set(
                evidence_map
            )
            -
            candidate_keys
        )

        if unknown_evidence_keys:

            raise ValueError(
                "Evidence observations were supplied "
                "for entity pairs that are not present "
                "in the candidate batch."
            )

        results: list[
            EntityResolutionResult
        ] = []

        for candidate in unique_candidates:

            pair_key = (
                self._candidate_pair_key(
                    candidate
                )
            )

            results.append(
                self.resolve_candidate(
                    candidate,
                    evidence_observations=(
                        evidence_map.get(
                            pair_key,
                            (),
                        )
                    ),
                )
            )

        results.sort(
            key=lambda result: (
                str(
                    result.first_entity_id
                ),
                str(
                    result.second_entity_id
                ),
            )
        )

        result_tuple = tuple(
            results
        )

        return (
            EntityResolutionBatchResult(
                results=result_tuple,
                input_candidate_count=(
                    input_candidate_count
                ),
                unique_candidate_count=(
                    len(
                        unique_candidates
                    )
                ),
                duplicate_candidate_count=(
                    duplicate_candidate_count
                ),
                match_count=(
                    self._decision_count(
                        result_tuple,
                        EntityResolutionDecision.MATCH,
                    )
                ),
                review_count=(
                    self._decision_count(
                        result_tuple,
                        EntityResolutionDecision.REVIEW,
                    )
                ),
                no_match_count=(
                    self._decision_count(
                        result_tuple,
                        EntityResolutionDecision.NO_MATCH,
                    )
                ),
                insufficient_count=(
                    self._decision_count(
                        result_tuple,
                        EntityResolutionDecision
                        .INSUFFICIENT,
                    )
                ),
            )
        )


    # ==========================================================
    # Single candidate
    # ==========================================================

    def resolve_candidate(
        self,
        candidate: EntityResolutionCandidate,
        *,
        evidence_observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None = None,
    ) -> EntityResolutionResult:
        """
        Resolve one candidate pair.

        Evidence observations are optional and are
        integrated as standard EVIDENCE resolution
        signals before scoring.

        Old calls without Evidence remain unchanged.

        This method is still completely non-destructive.
        """

        self._validate_candidate(
            candidate
        )

        first = (
            candidate.first_entity
        )

        second = (
            candidate.second_entity
        )

        evidence_bridge = (
            self._build_evidence_bridge(
                candidate,
                evidence_observations,
            )
        )

        # ======================================================
        # Signals
        # ======================================================

        signals = (
            self._build_signals(
                candidate
            )
        )

        if evidence_bridge.signals:

            signals.extend(
                evidence_bridge.signals
            )

            signals = (
                self._deduplicate_signals(
                    signals
                )
            )

        # ======================================================
        # Positive support
        # ======================================================

        support = (
            self.identity_scoring_service
            .score(
                signals
            )
        )

        # ======================================================
        # Contradictions
        # ======================================================

        contradiction = (
            self.contradiction_detection_service
            .detect(
                signals,
                entity_type=(
                    candidate.entity_type
                ),
            )
        )

        # ======================================================
        # Identity score + confidence
        # ======================================================

        confidence = (
            self.confidence_service
            .calculate(
                support,
                contradiction,
            )
        )

        # ======================================================
        # Decision
        # ======================================================

        policy_result = (
            self.decision_policy
            .evaluate(
                support=support,
                contradiction=(
                    contradiction
                ),
                confidence=confidence,
            )
        )

        # ======================================================
        # Explainable metadata
        # ======================================================

        metadata = {
            "candidate_generation": {
                "reasons": sorted(
                    set(
                        candidate.reasons
                    )
                ),
                "blocking_keys": sorted(
                    set(
                        candidate
                        .blocking_keys
                    )
                ),
            },
            "resolution_policy": {
                "rule_code": (
                    policy_result
                    .rule_code
                ),
                "message": (
                    policy_result
                    .message
                ),
                "identity_score": (
                    policy_result
                    .identity_score
                ),
                "confidence": (
                    policy_result
                    .confidence
                ),
                "support_score": (
                    policy_result
                    .support_score
                ),
                "contradiction_score": (
                    policy_result
                    .contradiction_score
                ),
                "evidence_strength": (
                    policy_result
                    .evidence_strength
                ),
                "support_signal_count": (
                    policy_result
                    .support_signal_count
                ),
                "contradiction_signal_count": (
                    policy_result
                    .contradiction_signal_count
                ),
                "strongest_support_strength": (
                    policy_result
                    .strongest_support_strength
                ),
                "hard_veto": (
                    policy_result
                    .hard_veto
                ),
            },
        }

        if (
            evidence_bridge
            .input_observation_count
            >
            0
        ):

            metadata[
                "evidence_bridge"
            ] = {
                "input_observation_count": (
                    evidence_bridge
                    .input_observation_count
                ),
                "unique_observation_count": (
                    evidence_bridge
                    .unique_observation_count
                ),
                "duplicate_observation_count": (
                    evidence_bridge
                    .duplicate_observation_count
                ),
                "supporting_observation_count": (
                    evidence_bridge
                    .supporting_observation_count
                ),
                "contradicting_observation_count": (
                    evidence_bridge
                    .contradicting_observation_count
                ),
                "neutral_observation_count": (
                    evidence_bridge
                    .neutral_observation_count
                ),
                "signal_count": len(
                    evidence_bridge.signals
                ),
                "strongest_support_evidence_id": (
                    str(
                        evidence_bridge
                        .strongest_support_evidence_id
                    )
                    if (
                        evidence_bridge
                        .strongest_support_evidence_id
                        is not None
                    )
                    else None
                ),
                "strongest_contradiction_evidence_id": (
                    str(
                        evidence_bridge
                        .strongest_contradiction_evidence_id
                    )
                    if (
                        evidence_bridge
                        .strongest_contradiction_evidence_id
                        is not None
                    )
                    else None
                ),
            }

        # ======================================================
        # Explainable result
        # ======================================================

        result = (
            self.explanation_service
            .build(
                first_entity_id=(
                    first.id
                ),
                second_entity_id=(
                    second.id
                ),
                decision=(
                    policy_result.decision
                ),
                signals=signals,
                support=support,
                contradiction=(
                    contradiction
                ),
                confidence=confidence,
                metadata=metadata,
            )
        )

        return result


    # ==========================================================
    # Signal generation
    # ==========================================================

    def _build_signals(
        self,
        candidate: EntityResolutionCandidate,
    ) -> list[
        EntityResolutionSignal
    ]:

        first = (
            candidate.first_entity
        )

        second = (
            candidate.second_entity
        )

        signals: list[
            EntityResolutionSignal
        ] = []

        signals.extend(
            self.exact_identifier_signal_builder
            .build(
                first,
                second,
            )
        )

        signals.extend(
            self.fuzzy_name_signal_builder
            .build(
                first,
                second,
            )
        )

        return self._deduplicate_signals(
            signals
        )

    # ==========================================================
    # Evidence bridge
    # ==========================================================

    def _build_evidence_bridge(
        self,
        candidate: EntityResolutionCandidate,
        observations: Iterable[
            EvidenceIdentityBridgeObservation
        ] | None,
    ) -> EvidenceIdentityBridgeResult:
        """
        Validate and convert optional Evidence observations
        for exactly one candidate pair.
        """

        observation_list = list(
            observations
            or ()
        )

        if not observation_list:

            return (
                self.evidence_bridge_service
                .build(
                    []
                )
            )

        expected_pair = (
            self._candidate_pair_key(
                candidate
            )
        )

        expected_case_id = getattr(
            candidate.first_entity,
            "case_id",
            None,
        )

        for observation in observation_list:

            if not isinstance(
                observation,
                EvidenceIdentityBridgeObservation,
            ):

                raise TypeError(
                    "evidence_observations must contain "
                    "only EvidenceIdentityBridgeObservation "
                    "objects."
                )

            observation_pair = tuple(
                sorted(
                    (
                        str(
                            observation
                            .first_entity_id
                        ),
                        str(
                            observation
                            .second_entity_id
                        ),
                    )
                )
            )

            if (
                observation_pair
                !=
                expected_pair
            ):

                raise ValueError(
                    "Evidence observation does not "
                    "belong to the candidate entity pair."
                )

            if (
                expected_case_id is None
                or
                observation.case_id
                !=
                expected_case_id
            ):

                raise ValueError(
                    "Evidence observation belongs to "
                    "a different investigation case."
                )

        return (
            self.evidence_bridge_service
            .build(
                observation_list
            )
        )

    @classmethod
    def _prepare_evidence_observations_by_pair(
        cls,
        observations_by_pair: (
            Mapping[
                tuple[str, str],
                Iterable[
                    EvidenceIdentityBridgeObservation
                ],
            ]
            | None
        ),
    ) -> dict[
        tuple[str, str],
        tuple[
            EvidenceIdentityBridgeObservation,
            ...,
        ],
    ]:
        """
        Normalize batch Evidence mapping.

        Pair direction is ignored:

            (A, B)
            (B, A)

        both normalize to the same canonical key.
        """

        if observations_by_pair is None:

            return {}

        if not isinstance(
            observations_by_pair,
            Mapping,
        ):

            raise TypeError(
                "evidence_observations_by_pair "
                "must be a mapping or None."
            )

        result: dict[
            tuple[str, str],
            list[
                EvidenceIdentityBridgeObservation
            ],
        ] = {}

        for (
            raw_pair,
            raw_observations,
        ) in observations_by_pair.items():

            if (
                not isinstance(
                    raw_pair,
                    tuple,
                )
                or
                len(
                    raw_pair
                )
                !=
                2
            ):

                raise TypeError(
                    "Evidence mapping keys must be "
                    "2-item entity-pair tuples."
                )

            first_id = str(
                raw_pair[
                    0
                ]
            ).strip()

            second_id = str(
                raw_pair[
                    1
                ]
            ).strip()

            if (
                not first_id
                or
                not second_id
            ):

                raise ValueError(
                    "Evidence mapping entity IDs "
                    "cannot be empty."
                )

            if (
                first_id
                ==
                second_id
            ):

                raise ValueError(
                    "Evidence mapping requires "
                    "two different entity IDs."
                )

            pair_key = tuple(
                sorted(
                    (
                        first_id,
                        second_id,
                    )
                )
            )

            observation_list = list(
                raw_observations
            )

            bucket = result.setdefault(
                pair_key,
                [],
            )

            bucket.extend(
                observation_list
            )

        return {
            pair_key: tuple(
                observations
            )
            for (
                pair_key,
                observations,
            )
            in result.items()
        }

    @staticmethod
    def _candidate_pair_key(
        candidate: EntityResolutionCandidate,
    ) -> tuple[
        str,
        str,
    ]:
        """
        Return deterministic entity-pair key.
        """

        first_id = getattr(
            candidate.first_entity,
            "id",
            None,
        )

        second_id = getattr(
            candidate.second_entity,
            "id",
            None,
        )

        if (
            first_id is None
            or
            second_id is None
        ):

            raise ValueError(
                "Candidate entities require IDs."
            )

        return tuple(
            sorted(
                (
                    str(
                        first_id
                    ),
                    str(
                        second_id
                    ),
                )
            )
        )


    # ==========================================================
    # Candidate preparation
    # ==========================================================

    def _prepare_candidates(
        self,
        candidates: list[
            EntityResolutionCandidate
        ],
    ) -> list[
        EntityResolutionCandidate
    ]:
        """
        Canonicalize pair direction and merge duplicate
        candidate metadata without mutating input objects.
        """

        unique: dict[
            tuple[str, str],
            EntityResolutionCandidate,
        ] = {}

        for candidate in candidates:

            self._validate_candidate(
                candidate
            )

            canonical = (
                self._canonical_candidate(
                    candidate
                )
            )

            pair_key = (
                canonical.identity_key
            )

            existing = unique.get(
                pair_key
            )

            if existing is None:

                unique[
                    pair_key
                ] = canonical

                continue

            for reason in canonical.reasons:

                existing.add_reason(
                    reason
                )

            for blocking_key in (
                canonical.blocking_keys
            ):

                existing.add_blocking_key(
                    blocking_key
                )

        result = list(
            unique.values()
        )

        for candidate in result:

            candidate.reasons.sort()

            candidate.blocking_keys.sort()

        result.sort(
            key=lambda candidate: (
                candidate.identity_key[
                    0
                ],
                candidate.identity_key[
                    1
                ],
            )
        )

        return result

    def _canonical_candidate(
        self,
        candidate: EntityResolutionCandidate,
    ) -> EntityResolutionCandidate:
        """
        Return a non-mutating candidate representation
        with deterministic entity order.
        """

        first = (
            candidate.first_entity
        )

        second = (
            candidate.second_entity
        )

        if (
            str(
                first.id
            )
            <=
            str(
                second.id
            )
        ):

            ordered_first = first
            ordered_second = second

        else:

            ordered_first = second
            ordered_second = first

        return EntityResolutionCandidate(
            first_entity=(
                ordered_first
            ),
            second_entity=(
                ordered_second
            ),
            reasons=sorted(
                set(
                    candidate.reasons
                )
            ),
            blocking_keys=sorted(
                set(
                    candidate
                    .blocking_keys
                )
            ),
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_candidate(
        candidate: EntityResolutionCandidate,
    ) -> None:

        if not isinstance(
            candidate,
            EntityResolutionCandidate,
        ):

            raise TypeError(
                "candidate must be an "
                "EntityResolutionCandidate."
            )

        first = (
            candidate.first_entity
        )

        second = (
            candidate.second_entity
        )

        if first is None or second is None:

            raise ValueError(
                "Resolution candidate requires "
                "two entities."
            )

        first_id = getattr(
            first,
            "id",
            None,
        )

        second_id = getattr(
            second,
            "id",
            None,
        )

        if (
            first_id is None
            or second_id is None
        ):

            raise ValueError(
                "Candidate entities require IDs."
            )

        if first_id == second_id:

            raise ValueError(
                "Entity cannot be resolved "
                "against itself."
            )

        first_case_id = getattr(
            first,
            "case_id",
            None,
        )

        second_case_id = getattr(
            second,
            "case_id",
            None,
        )

        if (
            first_case_id is None
            or second_case_id is None
        ):

            raise ValueError(
                "Candidate entities require "
                "case IDs."
            )

        if (
            first_case_id
            !=
            second_case_id
        ):

            raise ValueError(
                "Cross-case entity resolution "
                "is not allowed."
            )

        first_type = getattr(
            first,
            "entity_type",
            None,
        )

        second_type = getattr(
            second,
            "entity_type",
            None,
        )

        if (
            first_type
            !=
            second_type
        ):

            raise ValueError(
                "Candidate entities must have "
                "the same entity type."
            )

    # ==========================================================
    # Signal deduplication
    # ==========================================================

    @staticmethod
    def _deduplicate_signals(
        signals: list[
            EntityResolutionSignal
        ],
    ) -> list[
        EntityResolutionSignal
    ]:
        """
        Deduplicate equivalent machine-readable signals.

        The strongest representation wins.
        """

        unique: dict[
            tuple[
                str,
                str,
                str,
            ],
            EntityResolutionSignal,
        ] = {}

        for signal in signals:

            key = (
                signal.name,
                signal.signal_type.value,
                signal.direction.value,
            )

            existing = unique.get(
                key
            )

            if existing is None:

                unique[
                    key
                ] = signal

                continue

            existing_strength = (
                float(
                    existing.score
                )
                *
                float(
                    existing.weight
                )
            )

            new_strength = (
                float(
                    signal.score
                )
                *
                float(
                    signal.weight
                )
            )

            if (
                new_strength
                >
                existing_strength
            ):

                unique[
                    key
                ] = signal

        return sorted(
            unique.values(),
            key=lambda signal: (
                signal.signal_type.value,
                signal.direction.value,
                signal.name,
                -float(
                    signal.score
                ),
                -float(
                    signal.weight
                ),
            ),
        )

    # ==========================================================
    # Statistics
    # ==========================================================

    @staticmethod
    def _decision_count(
        results: tuple[
            EntityResolutionResult,
            ...,
        ],
        decision: (
            EntityResolutionDecision
        ),
    ) -> int:

        return sum(
            1
            for result
            in results
            if (
                result.decision
                ==
                decision
            )
        )