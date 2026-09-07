"""
Evidence contradiction detection.

Analyzes opposing Evidence observations for one
proposition.

Responsibilities:

- separate supporting and contradicting Evidence
- allow at most one contribution per Evidence per side
- detect cross-Evidence conflict
- calculate conservative support and contradiction strength
- calculate conflict overlap and severity
- preserve explicitly declared hard conflicts
- keep source independence separate
- return deterministic explainable breakdowns

Does NOT:

- calculate source reliability
- calculate corroboration
- assume Evidence sources are independent
- automatically infer hard conflicts
- calculate final evidence confidence
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from typing import (
    Any,
    Iterable,
)

from uuid import UUID

from app.evidence.contracts import (
    EvidenceSignal,
    EvidenceSignalDirection,
    EvidenceSignalType,
)


# ==========================================================
# Conflict severity
# ==========================================================


class EvidenceConflictSeverity(
    str,
    Enum,
):
    """
    Strength of disagreement between the
    SUPPORT and CONTRADICT sides.
    """

    NONE = "none"

    WEAK = "weak"

    MODERATE = "moderate"

    STRONG = "strong"

    CRITICAL = "critical"


# ==========================================================
# Observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceContradictionObservation:
    """
    One Evidence observation concerning a proposition.

    hard_conflict:

        Explicit marker supplied by an upstream
        domain-specific analyzer when the observation
        makes the proposition logically impossible.

    Important:

    hard_conflict is NEVER inferred merely because
    direction == CONTRADICT.
    """

    proposition_key: str

    signal: EvidenceSignal

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
                "Contradiction observation "
                "requires signal provenance."
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
            self.signal.direction
            !=
            EvidenceSignalDirection
            .CONTRADICT
        ):

            raise ValueError(
                "hard_conflict may only be "
                "attached to a CONTRADICT signal."
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

        return float(
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
class EvidenceContradictionConfig:
    """
    Conflict classification configuration.

    Counts do not automatically increase side strength.
    This prevents correlated Evidence from being treated
    as independent before Phase 2B.6.
    """

    moderate_threshold: float = 0.40

    strong_threshold: float = 0.70

    critical_threshold: float = 0.95

    balanced_margin: float = 0.10

    excluded_signal_types: frozenset[
        EvidenceSignalType
    ] = frozenset(
        {
            EvidenceSignalType.PROVENANCE,
            EvidenceSignalType.SOURCE,
            EvidenceSignalType.CORROBORATION,
            EvidenceSignalType.INDEPENDENCE,
        }
    )

    def __post_init__(
        self,
    ) -> None:

        thresholds = (
            self.moderate_threshold,
            self.strong_threshold,
            self.critical_threshold,
            self.balanced_margin,
        )

        for value in thresholds:

            if not (
                0.0
                <= float(
                    value
                )
                <= 1.0
            ):

                raise ValueError(
                    "Contradiction thresholds "
                    "must be between 0.0 and 1.0."
                )

        if not (
            self.moderate_threshold
            <=
            self.strong_threshold
            <=
            self.critical_threshold
        ):

            raise ValueError(
                "Conflict severity thresholds "
                "must be ordered."
            )


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceContradictionContribution:
    """
    One distinct Evidence contribution.
    """

    evidence_id: UUID

    source_id: UUID

    signal_name: str

    signal_type: EvidenceSignalType

    direction: EvidenceSignalDirection

    strength: float

    weight: float

    effective_strength: float

    hard_conflict: bool

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
class EvidenceContradictionBreakdown:
    """
    Explainable contradiction analysis.

    support_strength:
        Strongest distinct Evidence supporting
        the proposition.

    contradiction_strength:
        Strongest distinct Evidence contradicting
        the proposition.

    conflict_score:
        Overlap between the opposing sides.

        If both sides exist:

            min(
                support_strength,
                contradiction_strength
            )

        Otherwise:
            0.0

    Counts remain diagnostics until source independence
    is evaluated.
    """

    proposition_key: str

    support_strength: float

    contradiction_strength: float

    conflict_score: float

    decision_margin: float

    severity: EvidenceConflictSeverity

    contributions: tuple[
        EvidenceContradictionContribution,
        ...,
    ] = ()

    support_evidence_count: int = 0

    contradiction_evidence_count: int = 0

    distinct_source_count: int = 0

    support_source_count: int = 0

    contradiction_source_count: int = 0

    input_observation_count: int = 0

    duplicate_observation_count: int = 0

    excluded_stage_signal_count: int = 0

    excluded_neutral_count: int = 0

    internally_conflicted_evidence_count: int = 0

    hard_conflict: bool = False

    hard_conflict_evidence_ids: tuple[
        UUID,
        ...,
    ] = ()

    source_independence_applied: bool = False

    @property
    def has_support(
        self,
    ) -> bool:

        return (
            self.support_evidence_count
            >
            0
        )

    @property
    def has_contradiction(
        self,
    ) -> bool:

        return (
            self.contradiction_evidence_count
            >
            0
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
        EvidenceContradictionContribution
        | None
    ):

        support = [
            contribution
            for contribution
            in self.contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection
                .SUPPORT
            )
        ]

        if not support:

            return None

        return max(
            support,
            key=lambda contribution: (
                contribution
                .effective_strength,
                str(
                    contribution
                    .evidence_id
                ),
            ),
        )

    @property
    def strongest_contradiction(
        self,
    ) -> (
        EvidenceContradictionContribution
        | None
    ):

        contradictions = [
            contribution
            for contribution
            in self.contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection
                .CONTRADICT
            )
        ]

        if not contradictions:

            return None

        return max(
            contradictions,
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


class EvidenceContradictionDetectionService:
    """
    Analyze opposing Evidence observations.

    Conservative rules:

    - one Evidence contributes at most once
    - repeated signals from one Evidence do not
      increase side strength
    - several Evidence objects do not automatically
      reinforce a side before independence analysis
    - hard conflict requires an explicit marker
    """

    def __init__(
        self,
        config: (
            EvidenceContradictionConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EvidenceContradictionConfig()
        )

    # ==========================================================
    # Single proposition
    # ==========================================================

    def analyze(
        self,
        proposition_key: str,
        observations: Iterable[
            EvidenceContradictionObservation
        ],
    ) -> EvidenceContradictionBreakdown:
        """
        Analyze one proposition.
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
                EvidenceContradictionObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceContradictionObservation "
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
        # Group by Evidence
        # ======================================================

        grouped: dict[
            UUID,
            list[
                EvidenceContradictionObservation
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
            EvidenceContradictionContribution
        ] = []

        duplicate_observation_count = 0

        excluded_stage_signal_count = 0

        excluded_neutral_count = 0

        internally_conflicted_evidence_count = 0

        # ======================================================
        # One Evidence -> maximum one directional vote
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

            eligible_support: list[
                EvidenceContradictionObservation
            ] = []

            eligible_contradiction: list[
                EvidenceContradictionObservation
            ] = []

            for observation in evidence_observations:

                signal = (
                    observation.signal
                )

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

                if (
                    signal.direction
                    ==
                    EvidenceSignalDirection
                    .SUPPORT
                ):

                    eligible_support.append(
                        observation
                    )

                elif (
                    signal.direction
                    ==
                    EvidenceSignalDirection
                    .CONTRADICT
                ):

                    eligible_contradiction.append(
                        observation
                    )

            # Same Evidence simultaneously supporting
            # and contradicting the proposition is
            # internally ambiguous.
            #
            # It does not receive either external vote.
            if (
                eligible_support
                and
                eligible_contradiction
            ):

                internally_conflicted_evidence_count += 1

                duplicate_observation_count += (
                    len(
                        eligible_support
                    )
                    +
                    len(
                        eligible_contradiction
                    )
                    -
                    2
                )

                continue

            selected: (
                EvidenceContradictionObservation
                | None
            ) = None

            if eligible_support:

                duplicate_observation_count += (
                    len(
                        eligible_support
                    )
                    -
                    1
                )

                selected = self._select_strongest(
                    eligible_support
                )

            elif eligible_contradiction:

                duplicate_observation_count += (
                    len(
                        eligible_contradiction
                    )
                    -
                    1
                )

                selected = self._select_strongest(
                    eligible_contradiction
                )

            if selected is None:

                continue

            signal = (
                selected.signal
            )

            contributions.append(
                EvidenceContradictionContribution(
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
                        signal
                        .weighted_strength
                    ),
                    hard_conflict=(
                        selected.hard_conflict
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
        # Deterministic order
        # ======================================================

        contributions.sort(
            key=lambda contribution: (
                contribution
                .direction
                .value,
                str(
                    contribution
                    .evidence_id
                ),
                contribution
                .signal_type
                .value,
                contribution
                .signal_name,
            )
        )

        support = [
            contribution
            for contribution
            in contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection
                .SUPPORT
            )
        ]

        contradictions = [
            contribution
            for contribution
            in contributions
            if (
                contribution.direction
                ==
                EvidenceSignalDirection
                .CONTRADICT
            )
        ]

        # ======================================================
        # Conservative side strength
        #
        # Counts do not increase strength before Phase 2B.6.
        # ======================================================

        support_strength = (
            max(
                (
                    contribution
                    .effective_strength
                    for contribution
                    in support
                ),
                default=0.0,
            )
        )

        contradiction_strength = (
            max(
                (
                    contribution
                    .effective_strength
                    for contribution
                    in contradictions
                ),
                default=0.0,
            )
        )

        # ======================================================
        # Cross-side conflict
        # ======================================================

        if (
            support
            and
            contradictions
        ):

            conflict_score = min(
                support_strength,
                contradiction_strength,
            )

        else:

            conflict_score = 0.0

        decision_margin = abs(
            support_strength
            -
            contradiction_strength
        )

        severity = self._severity(
            conflict_score
        )

        # ======================================================
        # Explicit hard conflicts
        # ======================================================

        hard_conflict_evidence_ids = tuple(
            sorted(
                {
                    contribution
                    .evidence_id
                    for contribution
                    in contradictions
                    if contribution
                    .hard_conflict
                },
                key=str,
            )
        )

        hard_conflict = bool(
            hard_conflict_evidence_ids
        )

        # ======================================================
        # Source diagnostics
        # ======================================================

        distinct_source_count = len(
            {
                contribution.source_id
                for contribution
                in contributions
            }
        )

        support_source_count = len(
            {
                contribution.source_id
                for contribution
                in support
            }
        )

        contradiction_source_count = len(
            {
                contribution.source_id
                for contribution
                in contradictions
            }
        )

        return (
            EvidenceContradictionBreakdown(
                proposition_key=(
                    proposition_key
                ),
                support_strength=(
                    self._clamp(
                        support_strength
                    )
                ),
                contradiction_strength=(
                    self._clamp(
                        contradiction_strength
                    )
                ),
                conflict_score=(
                    self._clamp(
                        conflict_score
                    )
                ),
                decision_margin=(
                    self._clamp(
                        decision_margin
                    )
                ),
                severity=severity,
                contributions=tuple(
                    contributions
                ),
                support_evidence_count=(
                    len(
                        support
                    )
                ),
                contradiction_evidence_count=(
                    len(
                        contradictions
                    )
                ),
                distinct_source_count=(
                    distinct_source_count
                ),
                support_source_count=(
                    support_source_count
                ),
                contradiction_source_count=(
                    contradiction_source_count
                ),
                input_observation_count=(
                    len(
                        observation_list
                    )
                ),
                duplicate_observation_count=(
                    duplicate_observation_count
                ),
                excluded_stage_signal_count=(
                    excluded_stage_signal_count
                ),
                excluded_neutral_count=(
                    excluded_neutral_count
                ),
                internally_conflicted_evidence_count=(
                    internally_conflicted_evidence_count
                ),
                hard_conflict=(
                    hard_conflict
                ),
                hard_conflict_evidence_ids=(
                    hard_conflict_evidence_ids
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
            EvidenceContradictionObservation
        ],
    ) -> tuple[
        EvidenceContradictionBreakdown,
        ...,
    ]:
        """
        Analyze multiple propositions.
        """

        observation_list = list(
            observations
        )

        grouped: dict[
            str,
            list[
                EvidenceContradictionObservation
            ],
        ] = {}

        for observation in observation_list:

            if not isinstance(
                observation,
                EvidenceContradictionObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceContradictionObservation "
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
    # Selection
    # ==========================================================

    @staticmethod
    def _select_strongest(
        observations: list[
            EvidenceContradictionObservation
        ],
    ) -> EvidenceContradictionObservation:
        """
        Deterministically choose the strongest signal
        belonging to one Evidence.
        """

        return max(
            observations,
            key=lambda observation: (
                observation
                .effective_strength,

                int(
                    observation
                    .hard_conflict
                ),

                observation
                .signal
                .signal_type
                .value,

                observation
                .signal
                .name,

                observation
                .signal
                .reason,
            ),
        )

    # ==========================================================
    # Severity
    # ==========================================================

    def _severity(
        self,
        conflict_score: float,
    ) -> EvidenceConflictSeverity:

        if conflict_score <= 0.0:

            return (
                EvidenceConflictSeverity
                .NONE
            )

        if (
            conflict_score
            >=
            self.config
            .critical_threshold
        ):

            return (
                EvidenceConflictSeverity
                .CRITICAL
            )

        if (
            conflict_score
            >=
            self.config
            .strong_threshold
        ):

            return (
                EvidenceConflictSeverity
                .STRONG
            )

        if (
            conflict_score
            >=
            self.config
            .moderate_threshold
        ):

            return (
                EvidenceConflictSeverity
                .MODERATE
            )

        return (
            EvidenceConflictSeverity
            .WEAK
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