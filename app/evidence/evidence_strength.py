"""
Intrinsic evidence strength scoring.

Calculates the intrinsic analytical strength of one
Evidence object's signals.

Responsibilities:

- consume EvidenceSignal objects
- calculate weighted intrinsic signal strength
- exclude signals belonging to later analytical stages
- prevent repeated analyses of one Evidence object
  from artificially inflating evidence strength
- deduplicate equivalent signals
- return explainable strength breakdown

Does NOT:

- calculate source reliability
- calculate corroboration
- calculate contradictions
- calculate source independence
- calculate final evidence confidence
- assume signals are independent
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

import json

from math import (
    isfinite,
)

from app.evidence.contracts import (
    EvidenceSignal,
    EvidenceSignalCollection,
    EvidenceSignalDirection,
    EvidenceSignalType,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceStrengthConfig:
    """
    Intrinsic Evidence Strength configuration.

    Only signal types representing properties of the
    Evidence object itself participate in this stage.

    The following belong to later stages and therefore
    must NOT influence intrinsic strength yet:

        PROVENANCE
        SOURCE
        CORROBORATION
        CONTRADICTION
        INDEPENDENCE

    Important:

    Multiple analytical signals from the same Evidence
    object are NOT assumed to be independent.
    """

    excluded_signal_types: frozenset[
        EvidenceSignalType
    ] = frozenset(
        {
            EvidenceSignalType.PROVENANCE,
            EvidenceSignalType.SOURCE,
            EvidenceSignalType.CORROBORATION,
            EvidenceSignalType.CONTRADICTION,
            EvidenceSignalType.INDEPENDENCE,
        }
    )


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceStrengthContribution:
    """
    One intrinsic strength contribution.

    effective_strength:

        signal.strength
        *
        signal.weight

    Direction is preserved for explainability but does
    not change intrinsic magnitude.

    A strong contradictory CONTENT signal is still a
    strong piece of evidence; its contradiction semantics
    are processed separately later.
    """

    signal_name: str

    signal_type: EvidenceSignalType

    direction: EvidenceSignalDirection

    strength: float

    weight: float

    effective_strength: float

    reason: str = ""

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


# ==========================================================
# Strength breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceStrengthBreakdown:
    """
    Explainable intrinsic Evidence Strength result.

    intrinsic_strength:
        Conservative strength of the strongest eligible
        signal belonging to the Evidence itself.

        Range:
            0.0 .. 1.0

    mean_signal_strength:
        Diagnostic average of eligible effective signal
        strengths.

        It does NOT determine intrinsic_strength.

    Important:

    intrinsic_strength is NOT:

        - source reliability
        - corroboration
        - independence
        - final confidence
    """

    intrinsic_strength: float

    mean_signal_strength: float

    contributions: tuple[
        EvidenceStrengthContribution,
        ...,
    ] = ()

    input_signal_count: int = 0

    considered_signal_count: int = 0

    excluded_stage_signal_count: int = 0

    zero_strength_signal_count: int = 0

    duplicate_signal_count: int = 0

    @property
    def has_intrinsic_strength(
        self,
    ) -> bool:

        return (
            self.intrinsic_strength
            >
            0.0
        )

    @property
    def strongest_contribution(
        self,
    ) -> (
        EvidenceStrengthContribution
        | None
    ):

        if not self.contributions:

            return None

        return max(
            self.contributions,
            key=lambda contribution: (
                contribution
                .effective_strength,
                contribution
                .signal_type
                .value,
                contribution
                .signal_name,
            ),
        )


# ==========================================================
# Scoring service
# ==========================================================


class EvidenceStrengthScoringService:
    """
    Calculate intrinsic Evidence Strength.

    Conservative rule:

        intrinsic_strength =
            max(
                eligible effective strengths
            )

    This is deliberate.

    Signals extracted from the same Evidence object may
    be highly correlated. For example:

        sha256
        sha1
        md5
        phash
        dhash

    are several observations about the same file, not
    several independent pieces of evidence.

    Corroboration and independence are separate phases.
    """

    def __init__(
        self,
        config: (
            EvidenceStrengthConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EvidenceStrengthConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def score_collection(
        self,
        collection: EvidenceSignalCollection,
    ) -> EvidenceStrengthBreakdown:
        """
        Calculate intrinsic strength for one signal
        collection.
        """

        if not isinstance(
            collection,
            EvidenceSignalCollection,
        ):

            raise TypeError(
                "collection must be an "
                "EvidenceSignalCollection."
            )

        return self.score(
            collection.signals
        )

    def score(
        self,
        signals: list[
            EvidenceSignal
        ],
    ) -> EvidenceStrengthBreakdown:
        """
        Calculate intrinsic Evidence Strength.

        No source reliability, corroboration or
        independence is used here.
        """

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

        if not signals:

            return (
                EvidenceStrengthBreakdown(
                    intrinsic_strength=0.0,
                    mean_signal_strength=0.0,
                    input_signal_count=0,
                )
            )

        unique_signals: dict[
            tuple[
                str,
                str,
            ],
            EvidenceSignal,
        ] = {}

        excluded_stage_signal_count = 0

        zero_strength_signal_count = 0

        duplicate_signal_count = 0

        # ======================================================
        # Filter + deduplicate
        # ======================================================

        for signal in signals:

            if not isinstance(
                signal,
                EvidenceSignal,
            ):

                raise TypeError(
                    "signals must contain only "
                    "EvidenceSignal objects."
                )

            if (
                signal.signal_type
                in
                self.config
                .excluded_signal_types
            ):

                excluded_stage_signal_count += 1

                continue

            effective_strength = (
                self._effective_strength(
                    signal
                )
            )

            if effective_strength <= 0.0:

                zero_strength_signal_count += 1

                continue

            key = (
                signal.name,
                signal.signal_type.value,
            )

            existing = unique_signals.get(
                key
            )

            if existing is None:

                unique_signals[
                    key
                ] = signal

                continue

            duplicate_signal_count += 1

            existing_strength = (
                self._effective_strength(
                    existing
                )
            )

            if (
                effective_strength
                >
                existing_strength
            ):

                unique_signals[
                    key
                ] = signal

                continue

            if (
                effective_strength
                ==
                existing_strength
                and self._stable_signal_key(
                    signal
                )
                <
                self._stable_signal_key(
                    existing
                )
            ):

                unique_signals[
                    key
                ] = signal

        # ======================================================
        # Contributions
        # ======================================================

        contributions: list[
            EvidenceStrengthContribution
        ] = []

        for key in sorted(
            unique_signals
        ):

            signal = (
                unique_signals[
                    key
                ]
            )

            effective_strength = (
                self._effective_strength(
                    signal
                )
            )

            contributions.append(
                EvidenceStrengthContribution(
                    signal_name=signal.name,
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
                    effective_strength=(
                        effective_strength
                    ),
                    reason=signal.reason,
                )
            )

        # ======================================================
        # Aggregate
        # ======================================================

        if not contributions:

            intrinsic_strength = 0.0

            mean_signal_strength = 0.0

        else:

            strengths = [
                contribution
                .effective_strength
                for contribution
                in contributions
            ]

            # Conservative:
            #
            # several analyses of the same Evidence
            # do not automatically reinforce each other.
            intrinsic_strength = max(
                strengths
            )

            mean_signal_strength = (
                sum(
                    strengths
                )
                /
                len(
                    strengths
                )
            )

        return (
            EvidenceStrengthBreakdown(
                intrinsic_strength=(
                    self._clamp(
                        intrinsic_strength
                    )
                ),
                mean_signal_strength=(
                    self._clamp(
                        mean_signal_strength
                    )
                ),
                contributions=tuple(
                    contributions
                ),
                input_signal_count=(
                    input_signal_count
                ),
                considered_signal_count=(
                    len(
                        contributions
                    )
                ),
                excluded_stage_signal_count=(
                    excluded_stage_signal_count
                ),
                zero_strength_signal_count=(
                    zero_strength_signal_count
                ),
                duplicate_signal_count=(
                    duplicate_signal_count
                ),
            )
        )

    # ==========================================================
    # Effective strength
    # ==========================================================

    @staticmethod
    def _effective_strength(
        signal: EvidenceSignal,
    ) -> float:

        strength = float(
            signal.strength
        )

        weight = float(
            signal.weight
        )

        if (
            not isfinite(
                strength
            )
            or not isfinite(
                weight
            )
        ):

            return 0.0

        if (
            strength <= 0.0
            or weight <= 0.0
        ):

            return 0.0

        return (
            EvidenceStrengthScoringService
            ._clamp(
                strength
                *
                weight
            )
        )

    # ==========================================================
    # Deterministic tie-break
    # ==========================================================

    @staticmethod
    def _stable_signal_key(
        signal: EvidenceSignal,
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
    ]:

        provenance_origin = ""

        provenance_details = ""

        if signal.provenance is not None:

            provenance_origin = str(
                signal.provenance.origin
                or ""
            )

            provenance_details = json.dumps(
                signal.provenance.details,
                sort_keys=True,
                default=str,
                separators=(
                    ",",
                    ":",
                ),
            )

        details = json.dumps(
            signal.details,
            sort_keys=True,
            default=str,
            separators=(
                ",",
                ":",
            ),
        )

        return (
            signal.direction.value,
            signal.reason,
            provenance_origin,
            provenance_details,
            details,
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