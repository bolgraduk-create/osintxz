"""
Multi-signal entity identity scoring.

Aggregates positive entity-resolution signals into
one normalized identity support score.

Responsibilities:

- consume EntityResolutionSignal objects
- use SUPPORT signals only
- apply signal score and signal weight
- deduplicate signals by machine-readable name
- combine independent support conservatively
- return explainable score breakdown

Does NOT:

- detect contradictions
- calculate final resolution confidence
- decide MATCH / REVIEW / NO_MATCH
- merge entities
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from math import (
    isfinite,
    prod,
)

from app.entity_resolution.contracts import (
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
)


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityIdentityScoreContribution:
    """
    Contribution of one SUPPORT signal.

    effective_strength is:

        clamp(
            signal.score
            *
            signal.weight
        )

    This is an intermediate score,
    not a calibrated probability.
    """

    signal_name: str

    score: float

    weight: float

    effective_strength: float

    reason: str = ""

    details: dict = field(
        default_factory=dict
    )


# ==========================================================
# Score breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityIdentityScoreBreakdown:
    """
    Explainable positive identity score.

    support_score:
        Aggregated support in range 0..1.

    considered_signal_count:
        Number of unique SUPPORT signals
        actually used.

    ignored_signal_count:
        Number of NEUTRAL / CONTRADICT signals
        deliberately excluded from this phase.
    """

    support_score: float

    contributions: tuple[
        EntityIdentityScoreContribution,
        ...,
    ] = ()

    considered_signal_count: int = 0

    ignored_signal_count: int = 0

    duplicate_signal_count: int = 0

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
    def strongest_contribution(
        self,
    ) -> (
        EntityIdentityScoreContribution
        | None
    ):

        if not self.contributions:

            return None

        return max(
            self.contributions,
            key=lambda contribution: (
                contribution
                .effective_strength
            ),
        )


# ==========================================================
# Scoring service
# ==========================================================


class EntityIdentityScoringService:
    """
    Aggregate positive identity evidence.

    Combination uses a noisy-OR style formula:

        support =
            1 - product(
                1 - effective_strength
            )

    where:

        effective_strength =
            clamp(
                score * weight
            )

    Important:

    support_score is NOT a calibrated probability
    that two entities are the same real-world identity.

    Contradictions are intentionally handled later
    by a separate stage.
    """

    def score(
        self,
        signals: list[
            EntityResolutionSignal
        ],
    ) -> EntityIdentityScoreBreakdown:
        """
        Calculate positive multi-signal
        identity support.
        """

        if not signals:

            return (
                EntityIdentityScoreBreakdown(
                    support_score=0.0,
                )
            )

        support_signals: dict[
            str,
            EntityResolutionSignal,
        ] = {}

        ignored_signal_count = 0

        duplicate_signal_count = 0

        # ======================================================
        # Filter + deterministic deduplication
        # ======================================================

        for signal in signals:

            if (
                signal.direction
                !=
                EntityResolutionSignalDirection
                .SUPPORT
            ):

                ignored_signal_count += 1

                continue

            existing = support_signals.get(
                signal.name
            )

            if existing is None:

                support_signals[
                    signal.name
                ] = signal

                continue

            duplicate_signal_count += 1

            existing_strength = (
                self._effective_strength(
                    existing
                )
            )

            new_strength = (
                self._effective_strength(
                    signal
                )
            )

            # Keep strongest duplicate representation.
            if (
                new_strength
                >
                existing_strength
            ):

                support_signals[
                    signal.name
                ] = signal

        # ======================================================
        # Contributions
        # ======================================================

        contributions: list[
            EntityIdentityScoreContribution
        ] = []

        for name in sorted(
            support_signals
        ):

            signal = (
                support_signals[
                    name
                ]
            )

            effective_strength = (
                self._effective_strength(
                    signal
                )
            )

            if effective_strength <= 0.0:

                continue

            contributions.append(
                EntityIdentityScoreContribution(
                    signal_name=signal.name,
                    score=float(
                        signal.score
                    ),
                    weight=float(
                        signal.weight
                    ),
                    effective_strength=(
                        effective_strength
                    ),
                    reason=signal.reason,
                    details=dict(
                        signal.details
                    ),
                )
            )

        # ======================================================
        # Noisy-OR style aggregation
        # ======================================================

        if not contributions:

            support_score = 0.0

        else:

            remaining_non_support = prod(
                (
                    1.0
                    -
                    contribution
                    .effective_strength
                )
                for contribution
                in contributions
            )

            support_score = (
                1.0
                -
                remaining_non_support
            )

            support_score = (
                self._clamp(
                    support_score
                )
            )

        return EntityIdentityScoreBreakdown(
            support_score=(
                support_score
            ),
            contributions=tuple(
                contributions
            ),
            considered_signal_count=(
                len(
                    contributions
                )
            ),
            ignored_signal_count=(
                ignored_signal_count
            ),
            duplicate_signal_count=(
                duplicate_signal_count
            ),
        )

    # ==========================================================
    # Signal strength
    # ==========================================================

    def _effective_strength(
        self,
        signal: EntityResolutionSignal,
    ) -> float:

        score = float(
            signal.score
        )

        weight = float(
            signal.weight
        )

        if (
            not isfinite(
                score
            )
            or not isfinite(
                weight
            )
        ):

            return 0.0

        if (
            score <= 0.0
            or weight <= 0.0
        ):

            return 0.0

        return self._clamp(
            score
            *
            weight
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