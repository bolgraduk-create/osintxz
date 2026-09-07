"""
Entity resolution decision policy.

Converts already calculated identity-resolution metrics
into MATCH / REVIEW / NO_MATCH / INSUFFICIENT.

Responsibilities:

- apply conservative resolution thresholds
- protect against weak single-signal matches
- respect hard-veto contradictions
- keep ambiguous evidence in REVIEW
- preserve explainable policy rationale

Does NOT:

- generate signals
- calculate scores
- calculate confidence
- merge database entities
- access the database
"""

from __future__ import annotations

from dataclasses import dataclass

from app.entity_resolution.contracts import (
    EntityResolutionDecision,
)

from app.entity_resolution.contradiction_detection import (
    EntityContradictionBreakdown,
)

from app.entity_resolution.identity_scoring import (
    EntityIdentityScoreBreakdown,
)

from app.entity_resolution.resolution_confidence import (
    EntityResolutionConfidenceBreakdown,
    EntityResolutionEvidenceDirection,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityResolutionPolicyConfig:
    """
    Conservative decision thresholds.

    MATCH:
        Requires strong identity support,
        good confidence and little contradiction.

        A single signal may cause MATCH only when its
        effective strength is almost identity-defining.

    NO_MATCH:
        Hard veto always wins.

        Without hard veto, several strong independent
        contradictions are required. This prevents
        different account IDs alone from automatically
        proving that two PERSON entities are different
        real-world people.

    REVIEW:
        Used for conflicting or incomplete but meaningful
        evidence.

    INSUFFICIENT:
        Used when evidence is absent or extremely weak.
    """

    match_identity_threshold: float = 0.90

    match_support_threshold: float = 0.90

    match_confidence_threshold: float = 0.80

    maximum_match_contradiction: float = 0.15

    single_signal_match_strength: float = 0.95

    minimum_support_signals_for_match: int = 2

    no_match_contradiction_threshold: float = 0.90

    no_match_confidence_threshold: float = 0.80

    maximum_no_match_identity_score: float = 0.25

    minimum_non_veto_contradictions_for_no_match: int = 2

    insufficient_evidence_threshold: float = 0.25

    def __post_init__(
        self,
    ) -> None:

        unit_values = {
            "match_identity_threshold":
                self.match_identity_threshold,

            "match_support_threshold":
                self.match_support_threshold,

            "match_confidence_threshold":
                self.match_confidence_threshold,

            "maximum_match_contradiction":
                self.maximum_match_contradiction,

            "single_signal_match_strength":
                self.single_signal_match_strength,

            "no_match_contradiction_threshold":
                self.no_match_contradiction_threshold,

            "no_match_confidence_threshold":
                self.no_match_confidence_threshold,

            "maximum_no_match_identity_score":
                self.maximum_no_match_identity_score,

            "insufficient_evidence_threshold":
                self.insufficient_evidence_threshold,
        }

        for (
            name,
            value,
        ) in unit_values.items():

            if not (
                0.0
                <= float(value)
                <= 1.0
            ):

                raise ValueError(
                    f"{name} must be between "
                    "0.0 and 1.0."
                )

        if (
            self.minimum_support_signals_for_match
            < 1
        ):

            raise ValueError(
                "minimum_support_signals_for_match "
                "must be positive."
            )

        if (
            self.minimum_non_veto_contradictions_for_no_match
            < 1
        ):

            raise ValueError(
                "minimum_non_veto_contradictions_for_no_match "
                "must be positive."
            )


# ==========================================================
# Policy result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityResolutionPolicyEvaluation:
    """
    Explainable decision-policy result.
    """

    decision: EntityResolutionDecision

    rule_code: str

    message: str

    identity_score: float

    confidence: float

    support_score: float

    contradiction_score: float

    evidence_strength: float

    support_signal_count: int

    contradiction_signal_count: int

    strongest_support_strength: float

    hard_veto: bool

    @property
    def is_match(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision.MATCH
        )

    @property
    def requires_review(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision.REVIEW
        )


# ==========================================================
# Policy
# ==========================================================


class EntityResolutionDecisionPolicy:
    """
    Conservative entity resolution policy.

    Decision order matters:

        1. no evidence
        2. hard veto
        3. safe MATCH
        4. safe NO_MATCH
        5. very weak evidence
        6. REVIEW
    """

    def __init__(
        self,
        config: (
            EntityResolutionPolicyConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EntityResolutionPolicyConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def evaluate(
        self,
        *,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
    ) -> EntityResolutionPolicyEvaluation:
        """
        Choose a resolution decision.
        """

        strongest_support_strength = (
            self._strongest_support_strength(
                support
            )
        )

        # ======================================================
        # 1. No evidence
        # ======================================================

        if not confidence.has_evidence:

            return self._result(
                decision=(
                    EntityResolutionDecision
                    .INSUFFICIENT
                ),
                rule_code=(
                    "no_resolution_evidence"
                ),
                message=(
                    "No meaningful identity-resolution "
                    "evidence is available."
                ),
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                strongest_support_strength=(
                    strongest_support_strength
                ),
            )

        # ======================================================
        # 2. Hard veto
        # ======================================================

        if contradiction.hard_veto:

            return self._result(
                decision=(
                    EntityResolutionDecision
                    .NO_MATCH
                ),
                rule_code="hard_veto",
                message=(
                    "A hard identity contradiction "
                    "prevents a match."
                ),
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                strongest_support_strength=(
                    strongest_support_strength
                ),
            )

        # ======================================================
        # 3. Safe MATCH
        # ======================================================

        if self._can_match(
            support=support,
            contradiction=contradiction,
            confidence=confidence,
            strongest_support_strength=(
                strongest_support_strength
            ),
        ):

            return self._result(
                decision=(
                    EntityResolutionDecision
                    .MATCH
                ),
                rule_code=(
                    "strong_consistent_support"
                ),
                message=(
                    "Identity support is strong, "
                    "confidence is sufficient and "
                    "contradiction remains low."
                ),
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                strongest_support_strength=(
                    strongest_support_strength
                ),
            )

        # ======================================================
        # 4. Safe NO_MATCH without hard veto
        # ======================================================

        if self._can_no_match(
            contradiction=contradiction,
            confidence=confidence,
        ):

            return self._result(
                decision=(
                    EntityResolutionDecision
                    .NO_MATCH
                ),
                rule_code=(
                    "multiple_strong_contradictions"
                ),
                message=(
                    "Multiple strong contradictory "
                    "signals consistently oppose "
                    "the same-identity hypothesis."
                ),
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                strongest_support_strength=(
                    strongest_support_strength
                ),
            )

        # ======================================================
        # 5. Extremely weak evidence
        # ======================================================

        if (
            confidence.evidence_strength
            <
            self.config
            .insufficient_evidence_threshold
        ):

            return self._result(
                decision=(
                    EntityResolutionDecision
                    .INSUFFICIENT
                ),
                rule_code="weak_evidence",
                message=(
                    "Available resolution evidence "
                    "is too weak for a meaningful "
                    "identity decision."
                ),
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                strongest_support_strength=(
                    strongest_support_strength
                ),
            )

        # ======================================================
        # 6. REVIEW
        # ======================================================

        return self._result(
            decision=(
                EntityResolutionDecision
                .REVIEW
            ),
            rule_code=(
                "ambiguous_or_incomplete_evidence"
            ),
            message=(
                "The current evidence is meaningful "
                "but does not safely satisfy automatic "
                "MATCH or NO_MATCH policy."
            ),
            support=support,
            contradiction=contradiction,
            confidence=confidence,
            strongest_support_strength=(
                strongest_support_strength
            ),
        )

    # ==========================================================
    # MATCH
    # ==========================================================

    def _can_match(
        self,
        *,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
        strongest_support_strength: float,
    ) -> bool:

        if (
            confidence.dominant_direction
            !=
            EntityResolutionEvidenceDirection
            .SUPPORT
        ):

            return False

        if (
            confidence.identity_score
            <
            self.config
            .match_identity_threshold
        ):

            return False

        if (
            support.support_score
            <
            self.config
            .match_support_threshold
        ):

            return False

        if (
            confidence.confidence
            <
            self.config
            .match_confidence_threshold
        ):

            return False

        if (
            contradiction
            .contradiction_score
            >
            self.config
            .maximum_match_contradiction
        ):

            return False

        # ======================================================
        # Evidence qualification
        #
        # Either:
        #
        # - one almost identity-defining signal
        #
        # OR
        #
        # - multiple independent support signals
        # ======================================================

        if (
            strongest_support_strength
            >=
            self.config
            .single_signal_match_strength
        ):

            return True

        if (
            support.considered_signal_count
            >=
            self.config
            .minimum_support_signals_for_match
        ):

            return True

        return False

    # ==========================================================
    # NO_MATCH
    # ==========================================================

    def _can_no_match(
        self,
        *,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
    ) -> bool:
        """
        Conservative non-veto NO_MATCH.

        One strong metadata conflict alone is deliberately
        insufficient.

        This protects PERSON resolution from assumptions like:

            different Telegram account IDs
            =
            definitely different real-world person
        """

        if (
            confidence.dominant_direction
            !=
            EntityResolutionEvidenceDirection
            .CONTRADICT
        ):

            return False

        if (
            contradiction
            .contradiction_score
            <
            self.config
            .no_match_contradiction_threshold
        ):

            return False

        if (
            confidence.confidence
            <
            self.config
            .no_match_confidence_threshold
        ):

            return False

        if (
            confidence.identity_score
            >
            self.config
            .maximum_no_match_identity_score
        ):

            return False

        if (
            contradiction
            .considered_signal_count
            <
            self.config
            .minimum_non_veto_contradictions_for_no_match
        ):

            return False

        return True

    # ==========================================================
    # Result
    # ==========================================================

    @staticmethod
    def _result(
        *,
        decision: EntityResolutionDecision,
        rule_code: str,
        message: str,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
        strongest_support_strength: float,
    ) -> EntityResolutionPolicyEvaluation:

        return (
            EntityResolutionPolicyEvaluation(
                decision=decision,
                rule_code=rule_code,
                message=message,
                identity_score=(
                    confidence.identity_score
                ),
                confidence=(
                    confidence.confidence
                ),
                support_score=(
                    support.support_score
                ),
                contradiction_score=(
                    contradiction
                    .contradiction_score
                ),
                evidence_strength=(
                    confidence
                    .evidence_strength
                ),
                support_signal_count=(
                    support
                    .considered_signal_count
                ),
                contradiction_signal_count=(
                    contradiction
                    .considered_signal_count
                ),
                strongest_support_strength=(
                    strongest_support_strength
                ),
                hard_veto=(
                    contradiction.hard_veto
                ),
            )
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _strongest_support_strength(
        support: EntityIdentityScoreBreakdown,
    ) -> float:

        strongest = (
            support
            .strongest_contribution
        )

        if strongest is None:

            return 0.0

        return float(
            strongest
            .effective_strength
        )