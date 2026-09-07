"""
Explainable entity resolution result builder.

Combines previously calculated resolution artifacts
into one EntityResolutionResult.

Responsibilities:

- assemble signals
- assemble identity support score
- assemble contradiction analysis
- assemble resolution confidence
- generate human-readable reasons
- preserve detailed machine-readable diagnostics
- validate basic result consistency

Does NOT:

- generate candidate pairs
- generate resolution signals
- calculate support score
- detect contradictions
- calculate confidence
- choose MATCH / REVIEW / NO_MATCH
- merge entities
- access the database
"""

from __future__ import annotations

from typing import Any

from uuid import UUID

from app.entity_resolution.contracts import (
    EntityResolutionDecision,
    EntityResolutionReason,
    EntityResolutionResult,
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
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


class EntityResolutionExplanationService:
    """
    Build one complete explainable resolution result.

    Important:

    The decision is supplied by the caller.

    This service deliberately does not contain
    threshold policy.
    """

    _FLOAT_TOLERANCE = 1e-9

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        *,
        first_entity_id: UUID,
        second_entity_id: UUID,
        decision: EntityResolutionDecision,
        signals: list[
            EntityResolutionSignal
        ],
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
        metadata: dict[str, Any] | None = None,
    ) -> EntityResolutionResult:
        """
        Assemble EntityResolutionResult from already
        calculated resolution artifacts.
        """

        self._validate_consistency(
            decision=decision,
            support=support,
            contradiction=contradiction,
            confidence=confidence,
        )

        ordered_signals = (
            self._ordered_signals(
                signals
            )
        )

        reasons = (
            self._build_reasons(
                decision=decision,
                signals=ordered_signals,
                support=support,
                contradiction=contradiction,
                confidence=confidence,
            )
        )

        result_metadata = (
            self._build_metadata(
                support=support,
                contradiction=contradiction,
                confidence=confidence,
                metadata=metadata,
            )
        )

        return EntityResolutionResult(
            first_entity_id=(
                first_entity_id
            ),
            second_entity_id=(
                second_entity_id
            ),
            decision=decision,
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
            signals=list(
                ordered_signals
            ),
            reasons=reasons,
            metadata=(
                result_metadata
            ),
        )

    # ==========================================================
    # Explainability reasons
    # ==========================================================

    def _build_reasons(
        self,
        *,
        decision: EntityResolutionDecision,
        signals: list[
            EntityResolutionSignal
        ],
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
    ) -> list[
        EntityResolutionReason
    ]:

        reasons: list[
            EntityResolutionReason
        ] = []

        # ======================================================
        # Signal-level reasons
        # ======================================================

        for signal in signals:

            message = (
                signal.reason.strip()
                if signal.reason
                else self._default_signal_message(
                    signal
                )
            )

            details = dict(
                signal.details
            )

            details.update(
                {
                    "weight": (
                        signal.weight
                    ),
                    "weighted_score": (
                        signal.weighted_score
                    ),
                    "signed_contribution": (
                        signal
                        .signed_contribution
                    ),
                    "signal_type": (
                        signal
                        .signal_type
                        .value
                    ),
                }
            )

            reasons.append(
                EntityResolutionReason(
                    code=signal.name,
                    message=message,
                    direction=(
                        signal.direction
                    ),
                    signal_name=(
                        signal.name
                    ),
                    score=(
                        signal.score
                    ),
                    details=details,
                )
            )

        # ======================================================
        # No evidence
        # ======================================================

        if not confidence.has_evidence:

            reasons.append(
                EntityResolutionReason(
                    code=(
                        "insufficient_evidence"
                    ),
                    message=(
                        "No meaningful identity "
                        "resolution signals are "
                        "currently available."
                    ),
                    direction=(
                        EntityResolutionSignalDirection
                        .NEUTRAL
                    ),
                    score=0.0,
                )
            )

        # ======================================================
        # Conflicting evidence
        # ======================================================

        if confidence.is_conflicted:

            reasons.append(
                EntityResolutionReason(
                    code=(
                        "conflicting_evidence"
                    ),
                    message=(
                        "The resolution contains "
                        "both supporting and "
                        "contradictory signals."
                    ),
                    direction=(
                        EntityResolutionSignalDirection
                        .NEUTRAL
                    ),
                    score=(
                        confidence
                        .conflict_overlap
                    ),
                    details={
                        "support_score": (
                            support.support_score
                        ),
                        "contradiction_score": (
                            contradiction
                            .contradiction_score
                        ),
                        "conflict_overlap": (
                            confidence
                            .conflict_overlap
                        ),
                        "decision_margin": (
                            confidence
                            .decision_margin
                        ),
                    },
                )
            )

        # ======================================================
        # Hard veto
        # ======================================================

        if contradiction.hard_veto:

            reasons.append(
                EntityResolutionReason(
                    code="hard_veto",
                    message=(
                        "A logically incompatible "
                        "identity contradiction "
                        "prevents the entities from "
                        "being resolved as the same "
                        "atomic identity."
                    ),
                    direction=(
                        EntityResolutionSignalDirection
                        .CONTRADICT
                    ),
                    score=(
                        contradiction
                        .contradiction_score
                    ),
                    details={
                        "signals": list(
                            contradiction
                            .hard_veto_signal_names
                        ),
                    },
                )
            )

        # ======================================================
        # Dominant evidence direction
        # ======================================================

        dominant_reason = (
            self._dominant_direction_reason(
                confidence
            )
        )

        if dominant_reason is not None:

            reasons.append(
                dominant_reason
            )

        # ======================================================
        # Supplied decision explanation
        #
        # This explains the decision but does not choose it.
        # ======================================================

        reasons.append(
            self._decision_reason(
                decision=decision,
                confidence=confidence,
            )
        )

        return self._deduplicate_reasons(
            reasons
        )

    # ==========================================================
    # Dominant direction
    # ==========================================================

    def _dominant_direction_reason(
        self,
        confidence: (
            EntityResolutionConfidenceBreakdown
        ),
    ) -> (
        EntityResolutionReason
        | None
    ):

        direction = (
            confidence
            .dominant_direction
        )

        if (
            direction
            ==
            EntityResolutionEvidenceDirection
            .NONE
        ):

            return None

        if (
            direction
            ==
            EntityResolutionEvidenceDirection
            .SUPPORT
        ):

            return EntityResolutionReason(
                code="dominant_support",
                message=(
                    "Supporting identity signals "
                    "currently outweigh "
                    "contradictory signals."
                ),
                direction=(
                    EntityResolutionSignalDirection
                    .SUPPORT
                ),
                score=(
                    confidence.support_score
                ),
            )

        if (
            direction
            ==
            EntityResolutionEvidenceDirection
            .CONTRADICT
        ):

            return EntityResolutionReason(
                code=(
                    "dominant_contradiction"
                ),
                message=(
                    "Contradictory identity signals "
                    "currently outweigh supporting "
                    "signals."
                ),
                direction=(
                    EntityResolutionSignalDirection
                    .CONTRADICT
                ),
                score=(
                    confidence
                    .contradiction_score
                ),
            )

        return EntityResolutionReason(
            code="balanced_evidence",
            message=(
                "Supporting and contradictory "
                "identity evidence are currently "
                "approximately balanced."
            ),
            direction=(
                EntityResolutionSignalDirection
                .NEUTRAL
            ),
            score=(
                confidence
                .evidence_strength
            ),
        )

    # ==========================================================
    # Decision explanation
    # ==========================================================

    @staticmethod
    def _decision_reason(
        *,
        decision: (
            EntityResolutionDecision
        ),
        confidence: (
            EntityResolutionConfidenceBreakdown
        ),
    ) -> EntityResolutionReason:

        if (
            decision
            ==
            EntityResolutionDecision
            .MATCH
        ):

            message = (
                "The supplied resolution policy "
                "classified the entity pair "
                "as a match."
            )

            direction = (
                EntityResolutionSignalDirection
                .SUPPORT
            )

        elif (
            decision
            ==
            EntityResolutionDecision
            .NO_MATCH
        ):

            message = (
                "The supplied resolution policy "
                "classified the entity pair "
                "as not matching."
            )

            direction = (
                EntityResolutionSignalDirection
                .CONTRADICT
            )

        elif (
            decision
            ==
            EntityResolutionDecision
            .REVIEW
        ):

            message = (
                "The supplied resolution policy "
                "requires manual or additional "
                "review of this entity pair."
            )

            direction = (
                EntityResolutionSignalDirection
                .NEUTRAL
            )

        else:

            message = (
                "The supplied resolution policy "
                "found insufficient information "
                "for a resolution decision."
            )

            direction = (
                EntityResolutionSignalDirection
                .NEUTRAL
            )

        return EntityResolutionReason(
            code=(
                f"decision_"
                f"{decision.value}"
            ),
            message=message,
            direction=direction,
            score=(
                confidence.confidence
            ),
            details={
                "decision": (
                    decision.value
                ),
                "identity_score": (
                    confidence
                    .identity_score
                ),
                "confidence": (
                    confidence.confidence
                ),
            },
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def _build_metadata(
        self,
        *,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:

        result = dict(
            metadata
            or {}
        )

        result[
            "resolution_explanation"
        ] = {
            "support": {
                "score": (
                    support.support_score
                ),
                "considered_signal_count": (
                    support
                    .considered_signal_count
                ),
                "ignored_signal_count": (
                    support
                    .ignored_signal_count
                ),
                "duplicate_signal_count": (
                    support
                    .duplicate_signal_count
                ),
                "strongest_signal": (
                    support
                    .strongest_contribution
                    .signal_name
                    if (
                        support
                        .strongest_contribution
                        is not None
                    )
                    else None
                ),
                "contributions": [
                    {
                        "signal_name": (
                            contribution
                            .signal_name
                        ),
                        "score": (
                            contribution.score
                        ),
                        "weight": (
                            contribution.weight
                        ),
                        "effective_strength": (
                            contribution
                            .effective_strength
                        ),
                        "reason": (
                            contribution.reason
                        ),
                        "details": dict(
                            contribution.details
                        ),
                    }
                    for contribution
                    in support.contributions
                ],
            },

            "contradiction": {
                "score": (
                    contradiction
                    .contradiction_score
                ),
                "hard_veto": (
                    contradiction.hard_veto
                ),
                "hard_veto_signal_names": (
                    list(
                        contradiction
                        .hard_veto_signal_names
                    )
                ),
                "maximum_severity": (
                    contradiction
                    .maximum_severity
                ),
                "considered_signal_count": (
                    contradiction
                    .considered_signal_count
                ),
                "ignored_signal_count": (
                    contradiction
                    .ignored_signal_count
                ),
                "duplicate_signal_count": (
                    contradiction
                    .duplicate_signal_count
                ),
                "strongest_signal": (
                    contradiction
                    .strongest_contribution
                    .signal_name
                    if (
                        contradiction
                        .strongest_contribution
                        is not None
                    )
                    else None
                ),
                "contributions": [
                    {
                        "signal_name": (
                            contribution
                            .signal_name
                        ),
                        "score": (
                            contribution.score
                        ),
                        "weight": (
                            contribution.weight
                        ),
                        "effective_strength": (
                            contribution
                            .effective_strength
                        ),
                        "severity": (
                            contribution.severity
                        ),
                        "hard_veto": (
                            contribution.hard_veto
                        ),
                        "reason": (
                            contribution.reason
                        ),
                        "details": dict(
                            contribution.details
                        ),
                    }
                    for contribution
                    in contradiction
                    .contributions
                ],
            },

            "confidence": {
                "identity_score": (
                    confidence.identity_score
                ),
                "confidence": (
                    confidence.confidence
                ),
                "evidence_strength": (
                    confidence
                    .evidence_strength
                ),
                "conflict_overlap": (
                    confidence
                    .conflict_overlap
                ),
                "decision_margin": (
                    confidence
                    .decision_margin
                ),
                "signal_count_factor": (
                    confidence
                    .signal_count_factor
                ),
                "dominant_direction": (
                    confidence
                    .dominant_direction
                    .value
                ),
                "support_signal_count": (
                    confidence
                    .support_signal_count
                ),
                "contradiction_signal_count": (
                    confidence
                    .contradiction_signal_count
                ),
                "total_signal_count": (
                    confidence
                    .total_signal_count
                ),
                "hard_veto": (
                    confidence.hard_veto
                ),
                "hard_veto_applied": (
                    confidence
                    .hard_veto_applied
                ),
            },
        }

        return result

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_consistency(
        self,
        *,
        decision: EntityResolutionDecision,
        support: EntityIdentityScoreBreakdown,
        contradiction: EntityContradictionBreakdown,
        confidence: EntityResolutionConfidenceBreakdown,
    ) -> None:

        if not isinstance(
            decision,
            EntityResolutionDecision,
        ):

            raise TypeError(
                "decision must be an "
                "EntityResolutionDecision."
            )

        if not self._close(
            support.support_score,
            confidence.support_score,
        ):

            raise ValueError(
                "Support breakdown and confidence "
                "breakdown contain different "
                "support scores."
            )

        if not self._close(
            contradiction
            .contradiction_score,
            confidence
            .contradiction_score,
        ):

            raise ValueError(
                "Contradiction breakdown and "
                "confidence breakdown contain "
                "different contradiction scores."
            )

        if (
            contradiction.hard_veto
            !=
            confidence.hard_veto
        ):

            raise ValueError(
                "Hard-veto state is inconsistent "
                "between contradiction and "
                "confidence breakdowns."
            )

        # Logical consistency only.
        #
        # This is not threshold policy.
        if (
            decision
            ==
            EntityResolutionDecision.MATCH
            and contradiction.hard_veto
        ):

            raise ValueError(
                "MATCH cannot coexist with "
                "a hard identity veto."
            )

    # ==========================================================
    # Deterministic ordering
    # ==========================================================

    @staticmethod
    def _ordered_signals(
        signals: list[
            EntityResolutionSignal
        ],
    ) -> list[
        EntityResolutionSignal
    ]:

        return sorted(
            list(
                signals
            ),
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

    @staticmethod
    def _deduplicate_reasons(
        reasons: list[
            EntityResolutionReason
        ],
    ) -> list[
        EntityResolutionReason
    ]:

        result: list[
            EntityResolutionReason
        ] = []

        seen: set[
            tuple[
                str,
                str | None,
                str,
            ]
        ] = set()

        for reason in reasons:

            key = (
                reason.code,
                reason.signal_name,
                reason.message,
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            result.append(
                reason
            )

        return result

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _default_signal_message(
        signal: EntityResolutionSignal,
    ) -> str:

        return (
            "Resolution signal "
            f"'{signal.name}' was observed."
        )

    def _close(
        self,
        first: float,
        second: float,
    ) -> bool:

        return (
            abs(
                float(first)
                -
                float(second)
            )
            <=
            self._FLOAT_TOLERANCE
        )