"""
Entity resolution confidence model.

Combines positive identity support and contradiction
analysis into an explainable identity score and
resolution confidence.

Responsibilities:

- combine support and contradiction without
  simple arithmetic subtraction
- calculate contradiction-adjusted identity score
- estimate confidence in the available evidence
- account for conflicting evidence
- account for number of independent signals
- apply hard-veto semantics
- expose explainable intermediate values

Does NOT:

- generate resolution signals
- decide MATCH / REVIEW / NO_MATCH
- merge entities
- access the database
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum

from math import isfinite

from app.entity_resolution.contradiction_detection import (
    EntityContradictionBreakdown,
)

from app.entity_resolution.identity_scoring import (
    EntityIdentityScoreBreakdown,
)


# ==========================================================
# Dominant evidence direction
# ==========================================================


class EntityResolutionEvidenceDirection(
    str,
    Enum,
):
    """
    Dominant direction of current evidence.
    """

    SUPPORT = "support"

    CONTRADICT = "contradict"

    BALANCED = "balanced"

    NONE = "none"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityResolutionConfidenceConfig:
    """
    Configuration for resolution confidence.

    identity_contradiction_penalty:
        Controls how strongly contradictions attenuate
        positive identity support.

        Identity score:

            support
            *
            (
                1
                -
                penalty
                * contradiction
            )

        This is deliberately not:

            support - contradiction

        because subtraction behaves poorly near
        score boundaries.

    confidence_conflict_penalty:
        Controls how much simultaneous support and
        contradiction reduce confidence.

    signal_count_bonus:
        Small confidence bonus when several independent
        signals support the current evidence picture.

        This bonus is intentionally bounded.

    balanced_margin:
        Difference below which support and contradiction
        are considered approximately balanced.

    hard_veto_confidence_floor:
        Minimum confidence when a logically incompatible
        hard-veto contradiction exists.
    """

    identity_contradiction_penalty: float = 0.75

    confidence_conflict_penalty: float = 0.75

    signal_count_bonus: float = 0.15

    balanced_margin: float = 0.10

    hard_veto_confidence_floor: float = 0.95

    def __post_init__(
        self,
    ) -> None:

        values = {
            "identity_contradiction_penalty":
                self.identity_contradiction_penalty,

            "confidence_conflict_penalty":
                self.confidence_conflict_penalty,

            "signal_count_bonus":
                self.signal_count_bonus,

            "balanced_margin":
                self.balanced_margin,

            "hard_veto_confidence_floor":
                self.hard_veto_confidence_floor,
        }

        for (
            name,
            value,
        ) in values.items():

            if (
                not isfinite(
                    value
                )
                or not (
                    0.0
                    <= value
                    <= 1.0
                )
            ):

                raise ValueError(
                    f"{name} must be a finite "
                    "value between 0.0 and 1.0."
                )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityResolutionConfidenceBreakdown:
    """
    Explainable resolution-confidence result.

    identity_score:
        Contradiction-adjusted strength of the
        same-identity hypothesis.

    confidence:
        Confidence that the current evidence picture
        is sufficiently decisive.

        High confidence may occur for either:

        - strong identity support
        - strong contradiction

    evidence_strength:
        Overall amount of evidence present in either
        direction.

    conflict_overlap:
        Degree to which strong support and strong
        contradiction coexist.

    decision_margin:
        Distance between support and contradiction.

    signal_count_factor:
        Saturating factor representing additional
        independent evidence signals.
    """

    identity_score: float

    confidence: float

    support_score: float

    contradiction_score: float

    evidence_strength: float

    conflict_overlap: float

    decision_margin: float

    signal_count_factor: float

    dominant_direction: (
        EntityResolutionEvidenceDirection
    )

    support_signal_count: int

    contradiction_signal_count: int

    total_signal_count: int

    hard_veto: bool = False

    hard_veto_applied: bool = False

    @property
    def has_evidence(
        self,
    ) -> bool:

        return (
            self.total_signal_count
            >
            0
            or self.evidence_strength
            >
            0.0
        )

    @property
    def is_conflicted(
        self,
    ) -> bool:
        """
        Whether both directions contain
        meaningful evidence.
        """

        return (
            self.support_score > 0.0
            and
            self.contradiction_score > 0.0
        )


# ==========================================================
# Confidence service
# ==========================================================


class EntityResolutionConfidenceService:
    """
    Combine support and contradiction into
    explainable resolution metrics.

    Important:

    This service does NOT decide whether the
    final result is MATCH, REVIEW or NO_MATCH.

    That policy remains a separate stage.
    """

    def __init__(
        self,
        config: (
            EntityResolutionConfidenceConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EntityResolutionConfidenceConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def calculate(
        self,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
    ) -> EntityResolutionConfidenceBreakdown:
        """
        Calculate identity score and confidence.
        """

        support_score = self._clamp(
            support.support_score
        )

        contradiction_score = self._clamp(
            contradiction.contradiction_score
        )

        support_signal_count = max(
            0,
            int(
                support.considered_signal_count
            ),
        )

        contradiction_signal_count = max(
            0,
            int(
                contradiction
                .considered_signal_count
            ),
        )

        total_signal_count = (
            support_signal_count
            +
            contradiction_signal_count
        )

        # ======================================================
        # Evidence geometry
        # ======================================================

        evidence_strength = (
            1.0
            -
            (
                1.0
                -
                support_score
            )
            *
            (
                1.0
                -
                contradiction_score
            )
        )

        evidence_strength = self._clamp(
            evidence_strength
        )

        conflict_overlap = min(
            support_score,
            contradiction_score,
        )

        decision_margin = abs(
            support_score
            -
            contradiction_score
        )

        # ======================================================
        # Signal-count saturation
        #
        # 0 signals -> 0.0000
        # 1 signal  -> 0.5000
        # 2 signals -> 0.7500
        # 3 signals -> 0.8750
        # 4 signals -> 0.9375
        #
        # Additional signals have diminishing returns.
        # ======================================================

        if total_signal_count <= 0:

            signal_count_factor = 0.0

        else:

            signal_count_factor = (
                1.0
                -
                (
                    0.5
                    **
                    total_signal_count
                )
            )

        # ======================================================
        # Identity score
        #
        # Contradiction attenuates positive support,
        # but does not automatically erase it unless
        # hard veto exists.
        # ======================================================

        identity_multiplier = (
            1.0
            -
            (
                self.config
                .identity_contradiction_penalty
                *
                contradiction_score
            )
        )

        identity_multiplier = (
            self._clamp(
                identity_multiplier
            )
        )

        identity_score = (
            support_score
            *
            identity_multiplier
        )

        identity_score = self._clamp(
            identity_score
        )

        hard_veto_applied = False

        if contradiction.hard_veto:

            identity_score = 0.0

            hard_veto_applied = True

        # ======================================================
        # Confidence
        #
        # Strong evidence increases confidence.
        #
        # Simultaneously strong support and contradiction
        # reduce confidence because the evidence picture
        # becomes internally conflicted.
        # ======================================================

        dominant_strength = max(
            support_score,
            contradiction_score,
        )

        consistency_multiplier = (
            1.0
            -
            (
                self.config
                .confidence_conflict_penalty
                *
                conflict_overlap
            )
        )

        consistency_multiplier = (
            self._clamp(
                consistency_multiplier
            )
        )

        base_confidence = (
            dominant_strength
            *
            consistency_multiplier
        )

        base_confidence = self._clamp(
            base_confidence
        )

        # Small bounded benefit from several signals.
        confidence_bonus = (
            (
                1.0
                -
                base_confidence
            )
            *
            self.config
            .signal_count_bonus
            *
            signal_count_factor
        )

        confidence = (
            base_confidence
            +
            confidence_bonus
        )

        confidence = self._clamp(
            confidence
        )

        # ======================================================
        # Hard veto
        # ======================================================

        if contradiction.hard_veto:

            confidence = max(
                confidence,
                self.config
                .hard_veto_confidence_floor,
                contradiction_score,
            )

            confidence = self._clamp(
                confidence
            )

        # ======================================================
        # No evidence
        # ======================================================

        if (
            support_score == 0.0
            and contradiction_score == 0.0
            and total_signal_count == 0
        ):

            confidence = 0.0

            identity_score = 0.0

        # ======================================================
        # Dominant direction
        # ======================================================

        dominant_direction = (
            self._dominant_direction(
                support_score=(
                    support_score
                ),
                contradiction_score=(
                    contradiction_score
                ),
            )
        )

        return (
            EntityResolutionConfidenceBreakdown(
                identity_score=(
                    identity_score
                ),
                confidence=confidence,
                support_score=(
                    support_score
                ),
                contradiction_score=(
                    contradiction_score
                ),
                evidence_strength=(
                    evidence_strength
                ),
                conflict_overlap=(
                    conflict_overlap
                ),
                decision_margin=(
                    decision_margin
                ),
                signal_count_factor=(
                    signal_count_factor
                ),
                dominant_direction=(
                    dominant_direction
                ),
                support_signal_count=(
                    support_signal_count
                ),
                contradiction_signal_count=(
                    contradiction_signal_count
                ),
                total_signal_count=(
                    total_signal_count
                ),
                hard_veto=(
                    contradiction.hard_veto
                ),
                hard_veto_applied=(
                    hard_veto_applied
                ),
            )
        )

    # ==========================================================
    # Direction
    # ==========================================================

    def _dominant_direction(
        self,
        *,
        support_score: float,
        contradiction_score: float,
    ) -> EntityResolutionEvidenceDirection:

        if (
            support_score <= 0.0
            and
            contradiction_score <= 0.0
        ):

            return (
                EntityResolutionEvidenceDirection
                .NONE
            )

        if (
            support_score > 0.0
            and
            contradiction_score > 0.0
            and
            abs(
                support_score
                -
                contradiction_score
            )
            <=
            self.config
            .balanced_margin
        ):

            return (
                EntityResolutionEvidenceDirection
                .BALANCED
            )

        if (
            support_score
            >
            contradiction_score
        ):

            return (
                EntityResolutionEvidenceDirection
                .SUPPORT
            )

        return (
            EntityResolutionEvidenceDirection
            .CONTRADICT
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:

        if not isfinite(
            float(
                value
            )
        ):

            return 0.0

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )