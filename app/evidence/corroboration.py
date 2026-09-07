"""
Evidence corroboration analysis.

Measures agreement between distinct Evidence objects
supporting the same proposition.

Responsibilities:

- group observations by proposition
- require distinct Evidence objects for corroboration
- prevent multiple signals from one Evidence object
  from counting as multiple corroborators
- calculate raw corroboration strength
- preserve source diversity as diagnostics
- keep contradictions separate for the next stage
- return deterministic explainable breakdowns

Does NOT:

- calculate source reliability
- assume different Evidence objects are independent
- apply source-independence weighting
- calculate contradiction score
- calculate final evidence confidence
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

import math

from typing import (
    Any,
    Iterable,
)

from uuid import (
    UUID,
)

from app.evidence.contracts import (
    EvidenceSignal,
    EvidenceSignalDirection,
    EvidenceSignalType,
)


# ==========================================================
# Observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceCorroborationObservation:
    """
    One Evidence signal evaluated against
    one proposition.

    proposition_key:

        Stable machine-readable key describing
        the proposition being evaluated.

    Example:

        "person:123:owns_username:@example"

    The underlying EvidenceSignal must contain
    provenance because corroboration depends on
    distinguishing Evidence objects and Sources.
    """

    proposition_key: str

    signal: EvidenceSignal

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
            self.proposition_key,
            str,
        ):

            raise TypeError(
                "proposition_key must be "
                "a string."
            )

        if not self.proposition_key.strip():

            raise ValueError(
                "proposition_key cannot "
                "be empty."
            )

        if not isinstance(
            self.signal,
            EvidenceSignal,
        ):

            raise TypeError(
                "signal must be an "
                "EvidenceSignal."
            )

        if (
            self.signal.provenance
            is None
        ):

            raise ValueError(
                "Corroboration observation "
                "requires signal provenance."
            )

        if not isinstance(
            self.details,
            dict,
        ):

            raise TypeError(
                "details must be a dictionary."
            )

    @property
    def evidence_id(
        self,
    ) -> UUID:

        return (
            self.signal
            .provenance
            .evidence_id
        )

    @property
    def source_id(
        self,
    ) -> UUID:

        return (
            self.signal
            .provenance
            .source_id
        )

    @property
    def effective_strength(
        self,
    ) -> float:

        return (
            self.signal
            .weighted_strength
        )


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceCorroborationConfig:
    """
    Raw corroboration configuration.

    minimum_evidence_count:
        Number of distinct Evidence objects required
        before corroboration exists.

    count_decay:
        Controls diminishing returns from additional
        Evidence objects.

        count_factor:

            1 - count_decay ** (N - 1)

        Default 0.5 gives:

            N=1 -> 0.000
            N=2 -> 0.500
            N=3 -> 0.750
            N=4 -> 0.875

    Important:

    Source independence is deliberately NOT applied
    in this phase.
    """

    minimum_evidence_count: int = 2

    count_decay: float = 0.5

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

    def __post_init__(
        self,
    ) -> None:

        if (
            self.minimum_evidence_count
            <
            2
        ):

            raise ValueError(
                "minimum_evidence_count "
                "must be at least 2."
            )

        if (
            not math.isfinite(
                self.count_decay
            )
            or not (
                0.0
                <
                self.count_decay
                <
                1.0
            )
        ):

            raise ValueError(
                "count_decay must be "
                "between 0.0 and 1.0."
            )


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceCorroborationContribution:
    """
    One distinct Evidence object's contribution
    to raw corroboration.
    """

    evidence_id: UUID

    source_id: UUID

    signal_name: str

    signal_type: EvidenceSignalType

    strength: float

    weight: float

    effective_strength: float

    reason: str

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )


# ==========================================================
# Breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceCorroborationBreakdown:
    """
    Explainable raw corroboration result.

    corroboration_score:
        Agreement between distinct Evidence objects.

        It is NOT adjusted for source independence yet.

    agreement_strength:
        Mean effective strength of unique supporting
        Evidence objects.

    count_factor:
        Diminishing-return multiplier based on the
        number of unique supporting Evidence objects.

    source_diversity_ratio:
        Diagnostic only.

        Example:

            2 Evidence / 2 Sources -> 1.0
            2 Evidence / 1 Source  -> 0.5

        This value does NOT affect corroboration_score
        during Phase 2B.4.
    """

    proposition_key: str

    corroboration_score: float

    agreement_strength: float

    count_factor: float

    contributions: tuple[
        EvidenceCorroborationContribution,
        ...,
    ] = ()

    input_observation_count: int = 0

    supporting_evidence_count: int = 0

    distinct_source_count: int = 0

    source_diversity_ratio: float = 0.0

    duplicate_observation_count: int = 0

    excluded_stage_signal_count: int = 0

    excluded_contradiction_count: int = 0

    excluded_neutral_count: int = 0

    internally_conflicted_evidence_count: int = 0

    minimum_evidence_count: int = 2

    source_independence_applied: bool = False

    @property
    def is_corroborated(
        self,
    ) -> bool:

        return (
            self.supporting_evidence_count
            >=
            self.minimum_evidence_count
            and
            self.corroboration_score
            >
            0.0
        )

    @property
    def strongest_contribution(
        self,
    ) -> (
        EvidenceCorroborationContribution
        | None
    ):

        if not self.contributions:

            return None

        return max(
            self.contributions,
            key=lambda contribution: (
                contribution
                .effective_strength,
                str(
                    contribution
                    .evidence_id
                ),
            ),
        )


# ==========================================================
# Service
# ==========================================================


class EvidenceCorroborationService:
    """
    Calculate raw corroboration between
    distinct Evidence objects.

    One Evidence object receives at most one vote
    for one proposition.

    If the same Evidence contains both SUPPORT and
    CONTRADICT observations for the same proposition,
    it is considered internally conflicted and is
    excluded from corroboration.

    This prevents one Evidence item from supporting
    and contradicting the proposition simultaneously
    during this stage.
    """

    def __init__(
        self,
        config: (
            EvidenceCorroborationConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EvidenceCorroborationConfig()
        )

    # ==========================================================
    # Single proposition
    # ==========================================================

    def analyze(
        self,
        proposition_key: str,
        observations: Iterable[
            EvidenceCorroborationObservation
        ],
    ) -> EvidenceCorroborationBreakdown:
        """
        Analyze corroboration for one proposition.
        """

        proposition_key = str(
            proposition_key
        ).strip()

        if not proposition_key:

            raise ValueError(
                "proposition_key cannot "
                "be empty."
            )

        observation_list = list(
            observations
        )

        for observation in observation_list:

            if not isinstance(
                observation,
                EvidenceCorroborationObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceCorroborationObservation "
                    "objects."
                )

            if (
                observation.proposition_key
                !=
                proposition_key
            ):

                raise ValueError(
                    "All observations must belong "
                    "to the requested proposition."
                )

        # ======================================================
        # Group observations by Evidence
        # ======================================================

        grouped: dict[
            UUID,
            list[
                EvidenceCorroborationObservation
            ],
        ] = {}

        for observation in observation_list:

            grouped.setdefault(
                observation.evidence_id,
                [],
            ).append(
                observation
            )

        contributions: list[
            EvidenceCorroborationContribution
        ] = []

        duplicate_observation_count = 0

        excluded_stage_signal_count = 0

        excluded_contradiction_count = 0

        excluded_neutral_count = 0

        internally_conflicted_evidence_count = 0

        # ======================================================
        # One Evidence = maximum one corroboration vote
        # ======================================================

        for evidence_id in sorted(
            grouped,
            key=str,
        ):

            evidence_observations = (
                grouped[
                    evidence_id
                ]
            )

            has_support = any(
                observation.signal.direction
                ==
                EvidenceSignalDirection.SUPPORT
                for observation
                in evidence_observations
            )

            has_contradiction = any(
                observation.signal.direction
                ==
                EvidenceSignalDirection.CONTRADICT
                for observation
                in evidence_observations
            )

            # One Evidence cannot count simultaneously
            # as corroboration and contradiction.
            if (
                has_support
                and
                has_contradiction
            ):

                internally_conflicted_evidence_count += 1

                continue

            eligible_support: list[
                EvidenceCorroborationObservation
            ] = []

            for observation in evidence_observations:

                signal = (
                    observation.signal
                )

                if (
                    signal.direction
                    ==
                    EvidenceSignalDirection
                    .CONTRADICT
                ):

                    excluded_contradiction_count += 1

                    continue

                if (
                    signal.direction
                    ==
                    EvidenceSignalDirection
                    .NEUTRAL
                ):

                    excluded_neutral_count += 1

                    continue

                if (
                    signal.signal_type
                    in
                    self.config
                    .excluded_signal_types
                ):

                    excluded_stage_signal_count += 1

                    continue

                if (
                    signal.weighted_strength
                    <=
                    0.0
                ):

                    continue

                eligible_support.append(
                    observation
                )

            if not eligible_support:

                continue

            # Several signals from one Evidence do not
            # become several corroborators.
            if (
                len(
                    eligible_support
                )
                >
                1
            ):

                duplicate_observation_count += (
                    len(
                        eligible_support
                    )
                    -
                    1
                )

            selected = max(
                eligible_support,
                key=lambda observation: (
                    observation
                    .effective_strength,

                    observation
                    .signal
                    .signal_type
                    .value,

                    observation
                    .signal
                    .name,
                ),
            )

            signal = (
                selected.signal
            )

            contributions.append(
                EvidenceCorroborationContribution(
                    evidence_id=(
                        selected.evidence_id
                    ),
                    source_id=(
                        selected.source_id
                    ),
                    signal_name=(
                        signal.name
                    ),
                    signal_type=(
                        signal.signal_type
                    ),
                    strength=float(
                        signal.strength
                    ),
                    weight=float(
                        signal.weight
                    ),
                    effective_strength=(
                        float(
                            signal
                            .weighted_strength
                        )
                    ),
                    reason=(
                        signal.reason
                    ),
                    details={
                        **dict(
                            signal.details
                        ),
                        **dict(
                            selected.details
                        ),
                    },
                )
            )

        # ======================================================
        # Deterministic ordering
        # ======================================================

        contributions.sort(
            key=lambda contribution: (
                str(
                    contribution.evidence_id
                ),
                contribution.signal_type.value,
                contribution.signal_name,
            )
        )

        supporting_evidence_count = len(
            contributions
        )

        # ======================================================
        # Agreement strength
        # ======================================================

        if not contributions:

            agreement_strength = 0.0

        else:

            agreement_strength = (
                sum(
                    contribution
                    .effective_strength
                    for contribution
                    in contributions
                )
                /
                len(
                    contributions
                )
            )

        # ======================================================
        # Count saturation
        #
        # One Evidence does NOT constitute corroboration.
        # ======================================================

        if (
            supporting_evidence_count
            <
            self.config
            .minimum_evidence_count
        ):

            count_factor = 0.0

        else:

            count_factor = (
                1.0
                -
                (
                    self.config
                    .count_decay
                    **
                    (
                        supporting_evidence_count
                        -
                        1
                    )
                )
            )

        corroboration_score = (
            agreement_strength
            *
            count_factor
        )

        # ======================================================
        # Source diversity diagnostics
        #
        # NOT applied to score yet.
        # ======================================================

        distinct_source_ids = {
            contribution.source_id
            for contribution
            in contributions
        }

        distinct_source_count = len(
            distinct_source_ids
        )

        if supporting_evidence_count <= 0:

            source_diversity_ratio = 0.0

        else:

            source_diversity_ratio = (
                distinct_source_count
                /
                supporting_evidence_count
            )

        return (
            EvidenceCorroborationBreakdown(
                proposition_key=(
                    proposition_key
                ),
                corroboration_score=(
                    self._clamp(
                        corroboration_score
                    )
                ),
                agreement_strength=(
                    self._clamp(
                        agreement_strength
                    )
                ),
                count_factor=(
                    self._clamp(
                        count_factor
                    )
                ),
                contributions=tuple(
                    contributions
                ),
                input_observation_count=(
                    len(
                        observation_list
                    )
                ),
                supporting_evidence_count=(
                    supporting_evidence_count
                ),
                distinct_source_count=(
                    distinct_source_count
                ),
                source_diversity_ratio=(
                    self._clamp(
                        source_diversity_ratio
                    )
                ),
                duplicate_observation_count=(
                    duplicate_observation_count
                ),
                excluded_stage_signal_count=(
                    excluded_stage_signal_count
                ),
                excluded_contradiction_count=(
                    excluded_contradiction_count
                ),
                excluded_neutral_count=(
                    excluded_neutral_count
                ),
                internally_conflicted_evidence_count=(
                    internally_conflicted_evidence_count
                ),
                minimum_evidence_count=(
                    self.config
                    .minimum_evidence_count
                ),
                source_independence_applied=False,
            )
        )

    # ==========================================================
    # Multiple propositions
    # ==========================================================

    def analyze_many(
        self,
        observations: Iterable[
            EvidenceCorroborationObservation
        ],
    ) -> tuple[
        EvidenceCorroborationBreakdown,
        ...,
    ]:
        """
        Analyze multiple propositions deterministically.
        """

        observation_list = list(
            observations
        )

        grouped: dict[
            str,
            list[
                EvidenceCorroborationObservation
            ],
        ] = {}

        for observation in observation_list:

            if not isinstance(
                observation,
                EvidenceCorroborationObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceCorroborationObservation "
                    "objects."
                )

            grouped.setdefault(
                observation.proposition_key,
                [],
            ).append(
                observation
            )

        return tuple(
            self.analyze(
                proposition_key,
                grouped[
                    proposition_key
                ],
            )
            for proposition_key
            in sorted(
                grouped
            )
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