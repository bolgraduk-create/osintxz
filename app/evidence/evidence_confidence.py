"""
Evidence confidence aggregation.

Combines completed Evidence Analysis stages into one
explainable confidence score for a proposition.

Responsibilities:

- combine intrinsic evidence strength
- apply observed source-reliability penalties
- adjust corroboration by verified source independence
- combine base support and corroboration
- apply contradiction pressure
- enforce explicit hard-conflict veto
- expose analytical coverage
- preserve every intermediate component

Does NOT:

- calculate intrinsic Evidence Strength
- calculate Source Reliability
- calculate raw Corroboration
- detect Contradictions
- calculate Source Independence
- access the database
- make Entity Resolution decisions
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from app.evidence.evidence_strength import (
    EvidenceStrengthBreakdown,
)

from app.evidence.source_reliability import (
    SourceReliabilityBreakdown,
)

from app.evidence.corroboration import (
    EvidenceCorroborationBreakdown,
)

from app.evidence.contradiction_detection import (
    EvidenceContradictionBreakdown,
)

from app.evidence.source_independence import (
    EvidenceSourceIndependenceBreakdown,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceConfidenceConfig:
    """
    Evidence Confidence configuration.

    contradiction_penalty:
        Controls how strongly contradictory Evidence
        reduces proposition confidence.

        Default:
            1.0

        Therefore:

            contradiction_strength = 0.0
                -> no penalty

            contradiction_strength = 0.5
                -> 50% support remains

            contradiction_strength = 1.0
                -> support becomes 0

    Hard conflict always overrides this parameter.
    """

    contradiction_penalty: float = 1.0

    def __post_init__(
        self,
    ) -> None:

        value = float(
            self.contradiction_penalty
        )

        if not (
            0.0
            <= value
            <= 1.0
        ):

            raise ValueError(
                "contradiction_penalty must "
                "be between 0.0 and 1.0."
            )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceConfidenceBreakdown:
    """
    Explainable final Evidence Confidence result.

    confidence_score:
        Confidence that the evaluated proposition is
        supported by the currently available Evidence.

        Range:
            0.0 .. 1.0

    This is directional proposition confidence.

    A value near zero may mean:

        - weak support
        - strong contradiction
        - explicit hard conflict

    It does NOT mean the system has low confidence in
    the analytical decision itself.

    Component meanings remain separate.
    """

    proposition_key: str

    confidence_score: float

    # ------------------------------------------------------
    # Intrinsic Evidence
    # ------------------------------------------------------

    intrinsic_strength: float

    # ------------------------------------------------------
    # Source Reliability
    # ------------------------------------------------------

    source_reliability_score: float

    source_reliability_coverage: float

    source_quality_factor: float

    base_support_score: float

    # ------------------------------------------------------
    # Corroboration / Independence
    # ------------------------------------------------------

    raw_corroboration_score: float

    independence_score: float

    independence_coverage: float

    conservative_independence_score: float

    effective_corroboration_score: float

    support_before_contradiction: float

    # ------------------------------------------------------
    # Contradiction
    # ------------------------------------------------------

    contradiction_strength: float

    conflict_score: float

    contradiction_penalty_factor: float

    hard_conflict: bool

    # ------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------

    net_support_margin: float

    assessment_coverage: float

    corroboration_applied: bool

    independence_applicable: bool

    @property
    def has_support(
        self,
    ) -> bool:

        return (
            self.support_before_contradiction
            >
            0.0
        )

    @property
    def has_contradiction(
        self,
    ) -> bool:

        return (
            self.contradiction_strength
            >
            0.0
        )

    @property
    def is_conflicted(
        self,
    ) -> bool:

        return (
            self.has_support
            and
            self.has_contradiction
        )


# ==========================================================
# Aggregation service
# ==========================================================


class EvidenceConfidenceAggregationService:
    """
    Combine Evidence Analysis stages.

    Pipeline:

        intrinsic strength
                ↓
        source-quality adjustment
                ↓
        base support
                ↓
        corroboration
                ×
        verified independence
                ↓
        support aggregation
                ↓
        contradiction penalty
                ↓
        hard-conflict veto
                ↓
        final confidence
    """

    def __init__(
        self,
        config: (
            EvidenceConfidenceConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EvidenceConfidenceConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def aggregate(
        self,
        *,
        strength: EvidenceStrengthBreakdown,
        source_reliability: SourceReliabilityBreakdown,
        corroboration: EvidenceCorroborationBreakdown,
        contradiction: EvidenceContradictionBreakdown,
        independence: EvidenceSourceIndependenceBreakdown,
    ) -> EvidenceConfidenceBreakdown:
        """
        Aggregate all completed Evidence Analysis stages.

        No database writes are performed.
        """

        self._validate_inputs(
            strength=strength,
            source_reliability=(
                source_reliability
            ),
            corroboration=corroboration,
            contradiction=contradiction,
            independence=independence,
        )

        proposition_key = (
            corroboration.proposition_key
        )

        # ======================================================
        # 1. Intrinsic strength
        # ======================================================

        intrinsic_strength = (
            self._clamp(
                strength
                .intrinsic_strength
            )
        )

        # ======================================================
        # 2. Source reliability
        #
        # Missing reliability information is UNKNOWN,
        # not negative.
        #
        # Therefore only the OBSERVED fraction of the
        # model can penalize intrinsic support.
        #
        # factor =
        #
        #   1
        #   -
        #   coverage
        #   *
        #   (1 - reliability)
        #
        # ======================================================

        reliability_score = (
            self._clamp(
                source_reliability
                .reliability_score
            )
        )

        reliability_coverage = (
            self._clamp(
                source_reliability
                .coverage_score
            )
        )

        source_quality_factor = (
            1.0
            -
            (
                reliability_coverage
                *
                (
                    1.0
                    -
                    reliability_score
                )
            )
        )

        source_quality_factor = (
            self._clamp(
                source_quality_factor
            )
        )

        base_support_score = (
            intrinsic_strength
            *
            source_quality_factor
        )

        base_support_score = (
            self._clamp(
                base_support_score
            )
        )

        # ======================================================
        # 3. Corroboration adjusted by independence
        #
        # Raw agreement is not enough.
        #
        # Several Evidence objects derived from the same
        # primary source must not produce an independent
        # corroboration boost.
        # ======================================================

        raw_corroboration_score = (
            self._clamp(
                corroboration
                .corroboration_score
            )
        )

        independence_score = (
            self._clamp(
                independence
                .independence_score
            )
        )

        independence_coverage = (
            self._clamp(
                independence
                .coverage_score
            )
        )

        conservative_independence_score = (
            self._clamp(
                independence
                .conservative_independence_score
            )
        )

        independence_applicable = (
            independence
            .total_pair_count
            >
            0
        )

        if (
            raw_corroboration_score
            >
            0.0
            and
            independence_applicable
        ):

            effective_corroboration_score = (
                raw_corroboration_score
                *
                conservative_independence_score
            )

        else:

            effective_corroboration_score = 0.0

        effective_corroboration_score = (
            self._clamp(
                effective_corroboration_score
            )
        )

        corroboration_applied = (
            effective_corroboration_score
            >
            0.0
        )

        # ======================================================
        # 4. Support aggregation
        #
        # Noisy-OR between:
        #
        # - adjusted base Evidence
        # - verified-independent corroboration
        #
        # These are analytically different components,
        # unlike several hash algorithms of one file.
        # ======================================================

        support_before_contradiction = (
            1.0
            -
            (
                (
                    1.0
                    -
                    base_support_score
                )
                *
                (
                    1.0
                    -
                    effective_corroboration_score
                )
            )
        )

        support_before_contradiction = (
            self._clamp(
                support_before_contradiction
            )
        )

        # ======================================================
        # 5. Contradiction
        # ======================================================

        contradiction_strength = (
            self._clamp(
                contradiction
                .contradiction_strength
            )
        )

        conflict_score = (
            self._clamp(
                contradiction
                .conflict_score
            )
        )

        contradiction_penalty_factor = (
            1.0
            -
            (
                float(
                    self.config
                    .contradiction_penalty
                )
                *
                contradiction_strength
            )
        )

        contradiction_penalty_factor = (
            self._clamp(
                contradiction_penalty_factor
            )
        )

        # ======================================================
        # 6. Preliminary confidence
        # ======================================================

        confidence_score = (
            support_before_contradiction
            *
            contradiction_penalty_factor
        )

        confidence_score = (
            self._clamp(
                confidence_score
            )
        )

        # ======================================================
        # 7. Explicit hard conflict veto
        #
        # Hard conflict comes only from an upstream
        # analyzer that explicitly declared the
        # proposition impossible.
        # ======================================================

        hard_conflict = bool(
            contradiction
            .hard_conflict
        )

        if hard_conflict:

            confidence_score = 0.0

        # ======================================================
        # 8. Directional margin
        #
        # Diagnostic only.
        #
        # Range:
        #   -1 .. +1
        # ======================================================

        net_support_margin = (
            support_before_contradiction
            -
            contradiction_strength
        )

        net_support_margin = (
            self._clamp_signed(
                net_support_margin
            )
        )

        # ======================================================
        # 9. Assessment coverage
        #
        # Reliability coverage always applies.
        #
        # Independence coverage only applies when there
        # are multiple Evidence objects to compare.
        # ======================================================

        if independence_applicable:

            assessment_coverage = (
                (
                    reliability_coverage
                    +
                    independence_coverage
                )
                /
                2.0
            )

        else:

            assessment_coverage = (
                reliability_coverage
            )

        assessment_coverage = (
            self._clamp(
                assessment_coverage
            )
        )

        return (
            EvidenceConfidenceBreakdown(
                proposition_key=(
                    proposition_key
                ),
                confidence_score=(
                    confidence_score
                ),
                intrinsic_strength=(
                    intrinsic_strength
                ),
                source_reliability_score=(
                    reliability_score
                ),
                source_reliability_coverage=(
                    reliability_coverage
                ),
                source_quality_factor=(
                    source_quality_factor
                ),
                base_support_score=(
                    base_support_score
                ),
                raw_corroboration_score=(
                    raw_corroboration_score
                ),
                independence_score=(
                    independence_score
                ),
                independence_coverage=(
                    independence_coverage
                ),
                conservative_independence_score=(
                    conservative_independence_score
                ),
                effective_corroboration_score=(
                    effective_corroboration_score
                ),
                support_before_contradiction=(
                    support_before_contradiction
                ),
                contradiction_strength=(
                    contradiction_strength
                ),
                conflict_score=(
                    conflict_score
                ),
                contradiction_penalty_factor=(
                    contradiction_penalty_factor
                ),
                hard_conflict=(
                    hard_conflict
                ),
                net_support_margin=(
                    net_support_margin
                ),
                assessment_coverage=(
                    assessment_coverage
                ),
                corroboration_applied=(
                    corroboration_applied
                ),
                independence_applicable=(
                    independence_applicable
                ),
            )
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_inputs(
        *,
        strength: EvidenceStrengthBreakdown,
        source_reliability: SourceReliabilityBreakdown,
        corroboration: EvidenceCorroborationBreakdown,
        contradiction: EvidenceContradictionBreakdown,
        independence: EvidenceSourceIndependenceBreakdown,
    ) -> None:

        if not isinstance(
            strength,
            EvidenceStrengthBreakdown,
        ):

            raise TypeError(
                "strength must be an "
                "EvidenceStrengthBreakdown."
            )

        if not isinstance(
            source_reliability,
            SourceReliabilityBreakdown,
        ):

            raise TypeError(
                "source_reliability must be a "
                "SourceReliabilityBreakdown."
            )

        if not isinstance(
            corroboration,
            EvidenceCorroborationBreakdown,
        ):

            raise TypeError(
                "corroboration must be an "
                "EvidenceCorroborationBreakdown."
            )

        if not isinstance(
            contradiction,
            EvidenceContradictionBreakdown,
        ):

            raise TypeError(
                "contradiction must be an "
                "EvidenceContradictionBreakdown."
            )

        if not isinstance(
            independence,
            EvidenceSourceIndependenceBreakdown,
        ):

            raise TypeError(
                "independence must be an "
                "EvidenceSourceIndependenceBreakdown."
            )

        if (
            corroboration.proposition_key
            !=
            contradiction.proposition_key
        ):

            raise ValueError(
                "Corroboration and contradiction "
                "results belong to different "
                "propositions."
            )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )

    @staticmethod
    def _clamp_signed(
        value: float,
    ) -> float:

        return min(
            1.0,
            max(
                -1.0,
                float(
                    value
                ),
            ),
        )