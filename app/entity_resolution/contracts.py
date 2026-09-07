"""
Entity resolution contracts.

Defines shared data structures used by the
entity resolution pipeline.

Responsibilities:

- represent resolution signals
- represent supporting / contradictory evidence
- represent explainable resolution reasons
- represent final identity-resolution result
- define resolution decision states

Does NOT:

- compare entity values
- calculate fuzzy similarity
- calculate final scores
- access the database
- merge entities
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from typing import Any

from uuid import UUID


class EntityResolutionDecision(
    str,
    Enum,
):
    """
    Final entity resolution decision.
    """

    MATCH = "match"

    REVIEW = "review"

    NO_MATCH = "no_match"

    INSUFFICIENT = "insufficient"


class EntityResolutionSignalDirection(
    str,
    Enum,
):
    """
    Direction of an identity signal.
    """

    SUPPORT = "support"

    CONTRADICT = "contradict"

    NEUTRAL = "neutral"


class EntityResolutionSignalType(
    str,
    Enum,
):
    """
    High-level category of resolution signal.

    The enum is intentionally broad so later
    resolution stages can reuse one contract.
    """

    EXACT_IDENTIFIER = (
        "exact_identifier"
    )

    NAME_SIMILARITY = (
        "name_similarity"
    )

    VALUE_SIMILARITY = (
        "value_similarity"
    )

    METADATA_IDENTIFIER = (
        "metadata_identifier"
    )

    SOURCE = "source"

    EVIDENCE = "evidence"

    GRAPH = "graph"

    TEMPORAL = "temporal"

    CONTRADICTION = (
        "contradiction"
    )

    OTHER = "other"


@dataclass(
    slots=True,
)
class EntityResolutionSignal:
    """
    One machine-readable entity resolution signal.

    score:
        Strength of this particular signal
        in the normalized range [0.0, 1.0].

    weight:
        Relative importance used later by
        the scoring layer.

    The signal itself does not calculate the
    final identity score.
    """

    name: str

    signal_type: (
        EntityResolutionSignalType
    )

    direction: (
        EntityResolutionSignalDirection
    )

    score: float

    weight: float = 1.0

    reason: str = ""

    details: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.name = str(
            self.name
        ).strip()

        if not self.name:

            raise ValueError(
                "Resolution signal name "
                "cannot be empty."
            )

        self.score = float(
            self.score
        )

        self.weight = float(
            self.weight
        )

        self.reason = str(
            self.reason
            or ""
        ).strip()

        self._validate_unit_interval(
            self.score,
            field_name="score",
        )

        if self.weight < 0.0:

            raise ValueError(
                "Resolution signal weight "
                "cannot be negative."
            )

    @property
    def weighted_score(
        self,
    ) -> float:
        """
        Return unsigned weighted signal strength.

        This is an intermediate value only.
        """

        return (
            self.score
            *
            self.weight
        )

    @property
    def signed_contribution(
        self,
    ) -> float:
        """
        Return direction-aware intermediate
        signal contribution.

        SUPPORT:
            positive

        CONTRADICT:
            negative

        NEUTRAL:
            zero

        This is NOT the final identity score.
        """

        if (
            self.direction
            ==
            EntityResolutionSignalDirection
            .SUPPORT
        ):

            return (
                self.weighted_score
            )

        if (
            self.direction
            ==
            EntityResolutionSignalDirection
            .CONTRADICT
        ):

            return (
                -self.weighted_score
            )

        return 0.0

    @staticmethod
    def _validate_unit_interval(
        value: float,
        *,
        field_name: str,
    ) -> None:

        if not (
            0.0
            <= value
            <= 1.0
        ):

            raise ValueError(
                f"{field_name} must be "
                "between 0.0 and 1.0."
            )


@dataclass(
    slots=True,
)
class EntityResolutionReason:
    """
    Human-readable explanation for part
    of the resolution decision.

    Signals are primarily machine-readable.
    Reasons are designed for UI, reports,
    audit logs and future AI/RAG context.
    """

    code: str

    message: str

    direction: (
        EntityResolutionSignalDirection
    ) = (
        EntityResolutionSignalDirection
        .NEUTRAL
    )

    signal_name: str | None = None

    score: float | None = None

    details: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        self.code = str(
            self.code
        ).strip()

        self.message = str(
            self.message
        ).strip()

        if not self.code:

            raise ValueError(
                "Resolution reason code "
                "cannot be empty."
            )

        if not self.message:

            raise ValueError(
                "Resolution reason message "
                "cannot be empty."
            )

        if self.signal_name is not None:

            self.signal_name = str(
                self.signal_name
            ).strip() or None

        if self.score is not None:

            self.score = float(
                self.score
            )

            if not (
                0.0
                <= self.score
                <= 1.0
            ):

                raise ValueError(
                    "Resolution reason score "
                    "must be between "
                    "0.0 and 1.0."
                )


@dataclass(
    slots=True,
)
class EntityResolutionResult:
    """
    Complete result of comparing two entities.

    identity_score:
        Combined match strength.

        0.0 means no identity support.
        1.0 means maximum identity support.

        It is not automatically interpreted
        as a calibrated probability.

    confidence:
        Confidence in the final resolution
        decision itself.

    support_score:
        Aggregated positive support.

    contradiction_score:
        Aggregated contradictory support.

    These values are deliberately separate.
    """

    first_entity_id: UUID

    second_entity_id: UUID

    decision: EntityResolutionDecision

    identity_score: float

    confidence: float

    support_score: float = 0.0

    contradiction_score: float = 0.0

    signals: list[
        EntityResolutionSignal
    ] = field(
        default_factory=list
    )

    reasons: list[
        EntityResolutionReason
    ] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if (
            self.first_entity_id
            ==
            self.second_entity_id
        ):

            raise ValueError(
                "Entity resolution requires "
                "two different entity IDs."
            )

        self.identity_score = float(
            self.identity_score
        )

        self.confidence = float(
            self.confidence
        )

        self.support_score = float(
            self.support_score
        )

        self.contradiction_score = float(
            self.contradiction_score
        )

        self._validate_unit_interval(
            self.identity_score,
            field_name=(
                "identity_score"
            ),
        )

        self._validate_unit_interval(
            self.confidence,
            field_name="confidence",
        )

        self._validate_unit_interval(
            self.support_score,
            field_name=(
                "support_score"
            ),
        )

        self._validate_unit_interval(
            self.contradiction_score,
            field_name=(
                "contradiction_score"
            ),
        )

    # ==========================================================
    # Decision helpers
    # ==========================================================

    @property
    def is_match(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision
            .MATCH
        )

    @property
    def requires_review(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision
            .REVIEW
        )

    @property
    def is_no_match(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision
            .NO_MATCH
        )

    @property
    def is_insufficient(
        self,
    ) -> bool:

        return (
            self.decision
            ==
            EntityResolutionDecision
            .INSUFFICIENT
        )

    @property
    def is_final_decision(
        self,
    ) -> bool:
        """
        MATCH and NO_MATCH are considered
        final decisions.

        REVIEW and INSUFFICIENT require
        additional information or handling.
        """

        return self.decision in {
            EntityResolutionDecision.MATCH,
            EntityResolutionDecision.NO_MATCH,
        }

    # ==========================================================
    # Signal helpers
    # ==========================================================

    @property
    def supporting_signals(
        self,
    ) -> list[
        EntityResolutionSignal
    ]:

        return [
            signal
            for signal
            in self.signals
            if (
                signal.direction
                ==
                EntityResolutionSignalDirection
                .SUPPORT
            )
        ]

    @property
    def contradicting_signals(
        self,
    ) -> list[
        EntityResolutionSignal
    ]:

        return [
            signal
            for signal
            in self.signals
            if (
                signal.direction
                ==
                EntityResolutionSignalDirection
                .CONTRADICT
            )
        ]

    def add_signal(
        self,
        signal: EntityResolutionSignal,
    ) -> None:
        """
        Add an already calculated signal.

        This does not recalculate scores.
        """

        if not isinstance(
            signal,
            EntityResolutionSignal,
        ):

            raise TypeError(
                "signal must be an "
                "EntityResolutionSignal."
            )

        self.signals.append(
            signal
        )

    def add_reason(
        self,
        reason: EntityResolutionReason,
    ) -> None:
        """
        Add an explainability reason.
        """

        if not isinstance(
            reason,
            EntityResolutionReason,
        ):

            raise TypeError(
                "reason must be an "
                "EntityResolutionReason."
            )

        self.reasons.append(
            reason
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_unit_interval(
        value: float,
        *,
        field_name: str,
    ) -> None:

        if not (
            0.0
            <= value
            <= 1.0
        ):

            raise ValueError(
                f"{field_name} must be "
                "between 0.0 and 1.0."
            )