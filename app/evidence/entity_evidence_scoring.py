"""
Entity <-> Evidence association scoring.

Evaluates how strongly one Evidence object is associated
with one Entity.

Responsibilities:

- represent association signals
- aggregate supporting association evidence
- aggregate association contradictions
- prevent correlated signals from inflating scores
- distinguish association score from assessment confidence
- preserve explicit hard-conflict semantics
- provide deterministic explainable breakdowns

Does NOT:

- create EvidenceEntity database links
- delete EvidenceEntity links
- modify Entity or Evidence objects
- calculate general Evidence Confidence
- perform Entity Resolution
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from math import (
    isfinite,
)

from typing import Any

from uuid import UUID

from app.evidence.contracts import (
    EvidenceSignalDirection,
)


# ==========================================================
# Signal type
# ==========================================================


class EntityEvidenceAssociationSignalType(
    str,
    Enum,
):
    """
    Semantic type of an Entity <-> Evidence
    association signal.

    Signal type describes WHAT created the association.

    It does not determine the signal strength
    automatically.
    """

    EXACT_IDENTIFIER = "exact_identifier"

    METADATA_IDENTIFIER = "metadata_identifier"

    CONTENT_OCCURRENCE = "content_occurrence"

    EXPLICIT_LINK = "explicit_link"

    CONTEXT = "context"

    SEMANTIC = "semantic"

    TEMPORAL = "temporal"

    SPATIAL = "spatial"

    CONTRADICTION = "contradiction"

    OTHER = "other"


# ==========================================================
# Association signal
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityEvidenceAssociationSignal:
    """
    One explainable Entity <-> Evidence association
    signal.

    strength:
        Raw signal strength.

        Range:
            0.0 .. 1.0

    weight:
        Relative analytical importance.

        Range:
            0.0 .. 1.0

    effective_strength:
        strength * weight

    Important:

    An existing EvidenceEntity database link must NOT
    automatically mean association_score == 1.0.

    Example:

        EXPLICIT_LINK
        strength=1.0
        weight=0.65

    may represent a meaningful but not infallible
    existing/manual association.
    """

    name: str

    signal_type: (
        EntityEvidenceAssociationSignalType
    )

    direction: EvidenceSignalDirection

    strength: float

    weight: float = 1.0

    reason: str = ""

    hard_conflict: bool = False

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.name,
            str,
        ):

            raise TypeError(
                "Signal name must be a string."
            )

        if not self.name.strip():

            raise ValueError(
                "Signal name cannot be empty."
            )

        if not isinstance(
            self.signal_type,
            EntityEvidenceAssociationSignalType,
        ):

            raise TypeError(
                "signal_type must be an "
                "EntityEvidenceAssociationSignalType."
            )

        if not isinstance(
            self.direction,
            EvidenceSignalDirection,
        ):

            raise TypeError(
                "direction must be an "
                "EvidenceSignalDirection."
            )

        self._validate_unit_value(
            self.strength,
            field_name="strength",
        )

        self._validate_unit_value(
            self.weight,
            field_name="weight",
        )

        if not isinstance(
            self.reason,
            str,
        ):

            raise TypeError(
                "reason must be a string."
            )

        if not isinstance(
            self.hard_conflict,
            bool,
        ):

            raise TypeError(
                "hard_conflict must be bool."
            )

        if (
            self.hard_conflict
            and
            self.direction
            !=
            EvidenceSignalDirection.CONTRADICT
        ):

            raise ValueError(
                "hard_conflict may only be attached "
                "to a CONTRADICT signal."
            )

        if not isinstance(
            self.details,
            dict,
        ):

            raise TypeError(
                "details must be a dictionary."
            )

    @property
    def effective_strength(
        self,
    ) -> float:

        return (
            float(
                self.strength
            )
            *
            float(
                self.weight
            )
        )

    @property
    def is_support(
        self,
    ) -> bool:

        return (
            self.direction
            ==
            EvidenceSignalDirection.SUPPORT
        )

    @property
    def is_contradiction(
        self,
    ) -> bool:

        return (
            self.direction
            ==
            EvidenceSignalDirection.CONTRADICT
        )

    @property
    def is_neutral(
        self,
    ) -> bool:

        return (
            self.direction
            ==
            EvidenceSignalDirection.NEUTRAL
        )

    @staticmethod
    def _validate_unit_value(
        value: float,
        *,
        field_name: str,
    ) -> None:

        try:

            numeric_value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise TypeError(
                f"{field_name} must be numeric."
            ) from error

        if not isfinite(
            numeric_value
        ):

            raise ValueError(
                f"{field_name} must be finite."
            )

        if not (
            0.0
            <= numeric_value
            <= 1.0
        ):

            raise ValueError(
                f"{field_name} must be between "
                "0.0 and 1.0."
            )


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityEvidenceAssociationContribution:
    """
    One unique signal contribution after
    deduplication.
    """

    name: str

    signal_type: (
        EntityEvidenceAssociationSignalType
    )

    direction: EvidenceSignalDirection

    strength: float

    weight: float

    effective_strength: float

    reason: str

    hard_conflict: bool

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityEvidenceAssociationScoringConfig:
    """
    Association scoring configuration.

    secondary_signal_bonus:

        Secondary signals from ONE Evidence object
        are not assumed to be independent.

        The strongest signal forms the base.

        Remaining signals may only fill a bounded
        fraction of the remaining score headroom.

        Default:
            0.25

    contradiction_penalty:

        Controls how strongly contradictions reduce
        positive association.

    confidence_conflict_penalty:

        Reduces confidence when strong support and
        strong contradiction coexist.

    confidence_signal_count_bonus:

        Small diagnostic confidence bonus when several
        distinct analytical signals agree.

    hard_conflict_confidence_floor:

        Explicit hard conflicts can produce high
        confidence in a negative association result.
    """

    secondary_signal_bonus: float = 0.25

    contradiction_penalty: float = 0.85

    confidence_conflict_penalty: float = 0.75

    confidence_signal_count_bonus: float = 0.10

    hard_conflict_confidence_floor: float = 0.95

    def __post_init__(
        self,
    ) -> None:

        values = {
            "secondary_signal_bonus": (
                self.secondary_signal_bonus
            ),
            "contradiction_penalty": (
                self.contradiction_penalty
            ),
            "confidence_conflict_penalty": (
                self.confidence_conflict_penalty
            ),
            "confidence_signal_count_bonus": (
                self.confidence_signal_count_bonus
            ),
            "hard_conflict_confidence_floor": (
                self.hard_conflict_confidence_floor
            ),
        }

        for (
            name,
            value,
        ) in values.items():

            numeric = float(
                value
            )

            if (
                not isfinite(
                    numeric
                )
                or not (
                    0.0
                    <= numeric
                    <= 1.0
                )
            ):

                raise ValueError(
                    f"{name} must be between "
                    "0.0 and 1.0."
                )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityEvidenceAssociationResult:
    """
    Explainable Entity <-> Evidence association result.

    association_score:
        Strength of the positive relationship between
        this Evidence and this Entity.

    confidence:
        Confidence in the analytical assessment.

        Important:

        confidence may be high while association_score
        is low when strong contradictory information
        clearly rejects the association.

    support_score:
        Aggregated positive association strength.

    contradiction_score:
        Aggregated negative association strength.

    conflict_score:
        Overlap between support and contradiction.

    No database link is created by this result.
    """

    case_id: UUID

    entity_id: UUID

    evidence_id: UUID

    association_score: float

    confidence: float

    support_score: float

    contradiction_score: float

    conflict_score: float

    assessment_strength: float

    signal_count_factor: float

    hard_conflict: bool

    contributions: tuple[
        EntityEvidenceAssociationContribution,
        ...,
    ] = ()

    input_signal_count: int = 0

    considered_signal_count: int = 0

    supporting_signal_count: int = 0

    contradicting_signal_count: int = 0

    neutral_signal_count: int = 0

    duplicate_signal_count: int = 0

    hard_conflict_signal_names: tuple[
        str,
        ...,
    ] = ()

    @property
    def has_support(
        self,
    ) -> bool:

        return (
            self.support_score
            >
            0.0
        )

    @property
    def has_contradiction(
        self,
    ) -> bool:

        return (
            self.contradiction_score
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

    @property
    def strongest_support(
        self,
    ) -> (
        EntityEvidenceAssociationContribution
        | None
    ):

        candidates = [
            contribution
            for contribution
            in self.contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection.SUPPORT
            )
        ]

        if not candidates:

            return None

        return max(
            candidates,
            key=lambda contribution: (
                contribution.effective_strength,
                contribution.signal_type.value,
                contribution.name,
            ),
        )

    @property
    def strongest_contradiction(
        self,
    ) -> (
        EntityEvidenceAssociationContribution
        | None
    ):

        candidates = [
            contribution
            for contribution
            in self.contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection.CONTRADICT
            )
        ]

        if not candidates:

            return None

        return max(
            candidates,
            key=lambda contribution: (
                contribution.effective_strength,
                contribution.signal_type.value,
                contribution.name,
            ),
        )


# ==========================================================
# Scoring service
# ==========================================================


class EntityEvidenceAssociationScoringService:
    """
    Calculate association between one Entity
    and one Evidence object.

    Correlation safety:

        strongest signal
            +
        bounded secondary contribution

    Secondary signals are NOT aggregated with unlimited
    noisy-OR because all signals refer to the same
    Entity/Evidence pair and may be highly correlated.
    """

    def __init__(
        self,
        config: (
            EntityEvidenceAssociationScoringConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EntityEvidenceAssociationScoringConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def score(
        self,
        *,
        case_id: UUID,
        entity_id: UUID,
        evidence_id: UUID,
        signals: list[
            EntityEvidenceAssociationSignal
        ],
    ) -> EntityEvidenceAssociationResult:
        """
        Score one Entity <-> Evidence pair.

        No database writes are performed.
        """

        self._validate_uuid(
            case_id,
            field_name="case_id",
        )

        self._validate_uuid(
            entity_id,
            field_name="entity_id",
        )

        self._validate_uuid(
            evidence_id,
            field_name="evidence_id",
        )

        if not isinstance(
            signals,
            list,
        ):

            raise TypeError(
                "signals must be a list."
            )

        input_signal_count = len(
            signals
        )

        (
            unique_signals,
            duplicate_signal_count,
        ) = self._deduplicate_signals(
            signals
        )

        neutral_signal_count = sum(
            1
            for signal
            in unique_signals
            if signal.is_neutral
        )

        directional_signals = [
            signal
            for signal
            in unique_signals
            if not signal.is_neutral
            and signal.effective_strength > 0.0
        ]

        supporting_signals = [
            signal
            for signal
            in directional_signals
            if signal.is_support
        ]

        contradicting_signals = [
            signal
            for signal
            in directional_signals
            if signal.is_contradiction
        ]

        # ======================================================
        # Directional aggregation
        # ======================================================

        support_score = (
            self._aggregate_direction(
                supporting_signals
            )
        )

        contradiction_score = (
            self._aggregate_direction(
                contradicting_signals
            )
        )

        if (
            support_score > 0.0
            and
            contradiction_score > 0.0
        ):

            conflict_score = min(
                support_score,
                contradiction_score,
            )

        else:

            conflict_score = 0.0

        # ======================================================
        # Positive association score
        # ======================================================

        association_score = (
            support_score
            *
            (
                1.0
                -
                (
                    self.config
                    .contradiction_penalty
                    *
                    contradiction_score
                )
            )
        )

        association_score = (
            self._clamp(
                association_score
            )
        )

        # ======================================================
        # Explicit hard conflict
        # ======================================================

        hard_conflict_signals = [
            signal
            for signal
            in contradicting_signals
            if signal.hard_conflict
        ]

        hard_conflict = bool(
            hard_conflict_signals
        )

        if hard_conflict:

            association_score = 0.0

        hard_conflict_signal_names = tuple(
            sorted(
                {
                    signal.name
                    for signal
                    in hard_conflict_signals
                }
            )
        )

        # ======================================================
        # Assessment confidence
        #
        # Confidence means decisiveness, not positive
        # association probability.
        # ======================================================

        assessment_strength = max(
            support_score,
            contradiction_score,
        )

        conflict_overlap = min(
            support_score,
            contradiction_score,
        )

        considered_signal_count = len(
            directional_signals
        )

        if considered_signal_count <= 0:

            signal_count_factor = 0.0

        else:

            signal_count_factor = (
                1.0
                -
                (
                    0.5
                    **
                    considered_signal_count
                )
            )

        if assessment_strength <= 0.0:

            confidence = 0.0

        else:

            consistency_factor = (
                1.0
                -
                (
                    self.config
                    .confidence_conflict_penalty
                    *
                    conflict_overlap
                )
            )

            consistency_factor = (
                self._clamp(
                    consistency_factor
                )
            )

            base_confidence = (
                assessment_strength
                *
                consistency_factor
            )

            count_bonus = (
                self.config
                .confidence_signal_count_bonus
                *
                signal_count_factor
                *
                (
                    1.0
                    -
                    assessment_strength
                )
            )

            confidence = (
                base_confidence
                +
                count_bonus
            )

        confidence = (
            self._clamp(
                confidence
            )
        )

        if hard_conflict:

            confidence = max(
                confidence,
                self.config
                .hard_conflict_confidence_floor,
                contradiction_score,
            )

            confidence = (
                self._clamp(
                    confidence
                )
            )

        # ======================================================
        # Contributions
        # ======================================================

        contributions = tuple(
            EntityEvidenceAssociationContribution(
                name=signal.name,
                signal_type=(
                    signal.signal_type
                ),
                direction=(
                    signal.direction
                ),
                strength=float(
                    signal.strength
                ),
                weight=float(
                    signal.weight
                ),
                effective_strength=float(
                    signal.effective_strength
                ),
                reason=signal.reason,
                hard_conflict=(
                    signal.hard_conflict
                ),
                details=dict(
                    signal.details
                ),
            )
            for signal
            in sorted(
                directional_signals,
                key=self._stable_signal_key,
            )
        )

        return (
            EntityEvidenceAssociationResult(
                case_id=case_id,
                entity_id=entity_id,
                evidence_id=evidence_id,
                association_score=(
                    association_score
                ),
                confidence=confidence,
                support_score=(
                    support_score
                ),
                contradiction_score=(
                    contradiction_score
                ),
                conflict_score=(
                    conflict_score
                ),
                assessment_strength=(
                    assessment_strength
                ),
                signal_count_factor=(
                    signal_count_factor
                ),
                hard_conflict=(
                    hard_conflict
                ),
                contributions=(
                    contributions
                ),
                input_signal_count=(
                    input_signal_count
                ),
                considered_signal_count=(
                    considered_signal_count
                ),
                supporting_signal_count=(
                    len(
                        supporting_signals
                    )
                ),
                contradicting_signal_count=(
                    len(
                        contradicting_signals
                    )
                ),
                neutral_signal_count=(
                    neutral_signal_count
                ),
                duplicate_signal_count=(
                    duplicate_signal_count
                ),
                hard_conflict_signal_names=(
                    hard_conflict_signal_names
                ),
            )
        )

    # ==========================================================
    # Direction aggregation
    # ==========================================================

    def _aggregate_direction(
        self,
        signals: list[
            EntityEvidenceAssociationSignal
        ],
    ) -> float:
        """
        Aggregate correlated signals conservatively.

        Formula:

            dominant = strongest signal

            secondary =
                noisy-OR of remaining signals

            result =
                dominant
                +
                (1 - dominant)
                * secondary
                * secondary_signal_bonus

        Secondary signals therefore cannot consume more
        than a bounded fraction of the remaining score
        headroom.
        """

        if not signals:

            return 0.0

        strengths = sorted(
            (
                self._clamp(
                    signal.effective_strength
                )
                for signal
                in signals
                if signal.effective_strength > 0.0
            ),
            reverse=True,
        )

        if not strengths:

            return 0.0

        dominant = strengths[
            0
        ]

        if len(
            strengths
        ) == 1:

            return dominant

        remaining_product = 1.0

        for strength in strengths[
            1:
        ]:

            remaining_product *= (
                1.0
                -
                strength
            )

        secondary_strength = (
            1.0
            -
            remaining_product
        )

        result = (
            dominant
            +
            (
                1.0
                -
                dominant
            )
            *
            secondary_strength
            *
            self.config
            .secondary_signal_bonus
        )

        return self._clamp(
            result
        )

    # ==========================================================
    # Deduplication
    # ==========================================================

    def _deduplicate_signals(
        self,
        signals: list[
            EntityEvidenceAssociationSignal
        ],
    ) -> tuple[
        list[
            EntityEvidenceAssociationSignal
        ],
        int,
    ]:
        """
        Deduplicate equivalent machine signals.

        Same:
            name
            type
            direction

        -> strongest representation wins.
        """

        unique: dict[
            tuple[
                str,
                str,
                str,
            ],
            EntityEvidenceAssociationSignal,
        ] = {}

        duplicate_count = 0

        for signal in signals:

            if not isinstance(
                signal,
                EntityEvidenceAssociationSignal,
            ):

                raise TypeError(
                    "signals must contain only "
                    "EntityEvidenceAssociationSignal "
                    "objects."
                )

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

            duplicate_count += 1

            if (
                signal.effective_strength
                >
                existing.effective_strength
            ):

                unique[
                    key
                ] = signal

                continue

            if (
                signal.effective_strength
                ==
                existing.effective_strength
                and
                self._stable_signal_key(
                    signal
                )
                <
                self._stable_signal_key(
                    existing
                )
            ):

                unique[
                    key
                ] = signal

        return (
            [
                unique[
                    key
                ]
                for key
                in sorted(
                    unique
                )
            ],
            duplicate_count,
        )

    # ==========================================================
    # Deterministic ordering
    # ==========================================================

    @staticmethod
    def _stable_signal_key(
        signal: (
            EntityEvidenceAssociationSignal
        ),
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
    ]:

        return (
            signal.direction.value,
            signal.signal_type.value,
            signal.name,
            signal.reason,
            repr(
                sorted(
                    signal.details.items(),
                    key=lambda item: str(
                        item[
                            0
                        ]
                    ),
                )
            ),
        )

    # ==========================================================
    # Validation / helpers
    # ==========================================================

    @staticmethod
    def _validate_uuid(
        value: UUID,
        *,
        field_name: str,
    ) -> None:

        if not isinstance(
            value,
            UUID,
        ):

            raise TypeError(
                f"{field_name} must be UUID."
            )

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