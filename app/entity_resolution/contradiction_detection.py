"""
Entity resolution contradiction detection.

Aggregates contradictory identity signals into
an explainable contradiction score and determines
whether a contradiction represents a hard veto.

Responsibilities:

- consume CONTRADICT resolution signals
- aggregate contradiction strength
- classify contradiction severity
- detect safe entity-type-aware hard veto conditions
- deduplicate contradictory signals
- return explainable contradiction breakdown

Does NOT:

- generate identifier signals
- calculate positive identity support
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

from typing import Any

from app.entity_resolution.contracts import (
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
)

from app.models.entity import (
    EntityType,
)


# ==========================================================
# Severity
# ==========================================================


class EntityContradictionSeverity:
    """
    Stable string constants for contradiction severity.

    Kept intentionally simple because severity is an
    explanatory classification rather than a domain model.
    """

    WEAK = "weak"

    MODERATE = "moderate"

    STRONG = "strong"

    CRITICAL = "critical"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityContradictionConfig:
    """
    Contradiction aggregation configuration.

    Severity thresholds operate on effective strength:

        effective_strength =
            clamp(
                signal.score
                *
                signal.weight
            )

    Hard veto rules are deliberately conservative.

    Atomic entity types represent identifiers themselves.
    If their canonical identifier values conflict,
    they cannot represent the same atomic Entity.

    PERSON / ORGANIZATION are intentionally excluded.
    """

    moderate_threshold: float = 0.40

    strong_threshold: float = 0.70

    critical_threshold: float = 0.95

    hard_veto_entity_types: frozenset[
        EntityType
    ] = frozenset(
        {
            EntityType.EMAIL,
            EntityType.PHONE,
            EntityType.USERNAME,
            EntityType.DOMAIN,
            EntityType.URL,
            EntityType.IP,
            EntityType.ACCOUNT,
        }
    )

    metadata_hard_veto_threshold: float = 0.95

    def __post_init__(
        self,
    ) -> None:

        thresholds = (
            self.moderate_threshold,
            self.strong_threshold,
            self.critical_threshold,
            self.metadata_hard_veto_threshold,
        )

        for threshold in thresholds:

            if not (
                0.0
                <= threshold
                <= 1.0
            ):

                raise ValueError(
                    "Contradiction thresholds must "
                    "be between 0.0 and 1.0."
                )

        if not (
            self.moderate_threshold
            <=
            self.strong_threshold
            <=
            self.critical_threshold
        ):

            raise ValueError(
                "Contradiction severity thresholds "
                "must be ordered."
            )


# ==========================================================
# Contribution
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityContradictionContribution:
    """
    Contribution of one contradictory signal.
    """

    signal_name: str

    score: float

    weight: float

    effective_strength: float

    severity: str

    hard_veto: bool = False

    reason: str = ""

    details: dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# Breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EntityContradictionBreakdown:
    """
    Explainable contradiction analysis.

    contradiction_score:
        Combined contradiction strength in 0..1.

    hard_veto:
        Whether at least one contradiction makes
        identity equality impossible under the
        current entity-type semantics.

    Important:

    contradiction_score is NOT automatically
    subtracted from support_score here.

    Combination of support and contradiction belongs
    to later resolution-confidence / decision stages.
    """

    contradiction_score: float

    contributions: tuple[
        EntityContradictionContribution,
        ...,
    ] = ()

    hard_veto: bool = False

    hard_veto_signal_names: tuple[
        str,
        ...,
    ] = ()

    considered_signal_count: int = 0

    ignored_signal_count: int = 0

    duplicate_signal_count: int = 0

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
    def strongest_contribution(
        self,
    ) -> (
        EntityContradictionContribution
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

    @property
    def maximum_severity(
        self,
    ) -> str | None:

        strongest = (
            self.strongest_contribution
        )

        if strongest is None:

            return None

        return strongest.severity


# ==========================================================
# Detection service
# ==========================================================


class EntityContradictionDetectionService:
    """
    Analyze contradictory entity-resolution signals.

    Contradiction aggregation uses a noisy-OR style
    formula analogous to positive support aggregation:

        contradiction =
            1 - product(
                1 - effective_strength
            )

    This preserves several desirable properties:

    - output remains in 0..1
    - several independent contradictions reinforce
      each other
    - one critical contradiction can dominate
    - no arbitrary arithmetic subtraction from support
    """

    def __init__(
        self,
        config: (
            EntityContradictionConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EntityContradictionConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def detect(
        self,
        signals: list[
            EntityResolutionSignal
        ],
        *,
        entity_type: (
            EntityType
            | str
            | None
        ) = None,
    ) -> EntityContradictionBreakdown:
        """
        Analyze contradictory signals.

        entity_type describes the type of Entity pair
        currently being resolved.

        It is used only for safe hard-veto policy.
        """

        resolved_entity_type = (
            self._resolve_entity_type(
                entity_type
            )
        )

        if not signals:

            return (
                EntityContradictionBreakdown(
                    contradiction_score=0.0,
                )
            )

        contradictory_signals: dict[
            str,
            EntityResolutionSignal,
        ] = {}

        ignored_signal_count = 0

        duplicate_signal_count = 0

        # ======================================================
        # Filter contradictory signals
        # ======================================================

        for signal in signals:

            if (
                signal.direction
                !=
                EntityResolutionSignalDirection
                .CONTRADICT
            ):

                ignored_signal_count += 1

                continue

            existing = (
                contradictory_signals.get(
                    signal.name
                )
            )

            if existing is None:

                contradictory_signals[
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

            if (
                new_strength
                >
                existing_strength
            ):

                contradictory_signals[
                    signal.name
                ] = signal

        # ======================================================
        # Build contributions
        # ======================================================

        contributions: list[
            EntityContradictionContribution
        ] = []

        hard_veto_signal_names: list[
            str
        ] = []

        for signal_name in sorted(
            contradictory_signals
        ):

            signal = (
                contradictory_signals[
                    signal_name
                ]
            )

            effective_strength = (
                self._effective_strength(
                    signal
                )
            )

            if effective_strength <= 0.0:

                continue

            severity = (
                self._severity(
                    effective_strength
                )
            )

            hard_veto = (
                self._is_hard_veto(
                    signal=signal,
                    entity_type=(
                        resolved_entity_type
                    ),
                    effective_strength=(
                        effective_strength
                    ),
                )
            )

            if hard_veto:

                hard_veto_signal_names.append(
                    signal.name
                )

            contributions.append(
                EntityContradictionContribution(
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
                    severity=severity,
                    hard_veto=hard_veto,
                    reason=signal.reason,
                    details=dict(
                        signal.details
                    ),
                )
            )

        # ======================================================
        # Aggregate contradiction
        # ======================================================

        if not contributions:

            contradiction_score = 0.0

        else:

            remaining_non_contradiction = prod(
                (
                    1.0
                    -
                    contribution
                    .effective_strength
                )
                for contribution
                in contributions
            )

            contradiction_score = (
                1.0
                -
                remaining_non_contradiction
            )

            contradiction_score = (
                self._clamp(
                    contradiction_score
                )
            )

        return EntityContradictionBreakdown(
            contradiction_score=(
                contradiction_score
            ),
            contributions=tuple(
                contributions
            ),
            hard_veto=bool(
                hard_veto_signal_names
            ),
            hard_veto_signal_names=tuple(
                sorted(
                    hard_veto_signal_names
                )
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
    # Hard-veto policy
    # ==========================================================

    def _is_hard_veto(
        self,
        *,
        signal: EntityResolutionSignal,
        entity_type: EntityType | None,
        effective_strength: float,
    ) -> bool:
        """
        Determine whether a contradiction makes identity
        equality impossible under current Entity semantics.

        Rule 1:
            Canonical value conflicts for atomic Entity
            types are hard vetoes.

            EMAIL A != EMAIL B means they cannot be the
            same EMAIL entity.

        Rule 2:
            Very strong metadata-ID conflicts may hard-veto
            ACCOUNT entities.

        PERSON / ORGANIZATION metadata conflicts are NOT
        hard vetoes because one real-world identity may own
        multiple accounts.
        """

        if entity_type is None:

            return False

        # ======================================================
        # Exact canonical conflict of atomic entity itself
        # ======================================================

        expected_conflict_name = (
            f"{entity_type.value}"
            "_conflict"
        )

        if (
            entity_type
            in self.config
            .hard_veto_entity_types
            and signal.name
            ==
            expected_conflict_name
        ):

            return True

        # ======================================================
        # ACCOUNT metadata identity conflict
        # ======================================================

        if (
            entity_type
            ==
            EntityType.ACCOUNT
            and effective_strength
            >=
            self.config
            .metadata_hard_veto_threshold
            and (
                signal.name.startswith(
                    "metadata_"
                )
            )
        ):

            return True

        return False

    # ==========================================================
    # Severity
    # ==========================================================

    def _severity(
        self,
        effective_strength: float,
    ) -> str:

        if (
            effective_strength
            >=
            self.config
            .critical_threshold
        ):

            return (
                EntityContradictionSeverity
                .CRITICAL
            )

        if (
            effective_strength
            >=
            self.config
            .strong_threshold
        ):

            return (
                EntityContradictionSeverity
                .STRONG
            )

        if (
            effective_strength
            >=
            self.config
            .moderate_threshold
        ):

            return (
                EntityContradictionSeverity
                .MODERATE
            )

        return (
            EntityContradictionSeverity
            .WEAK
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
    def _resolve_entity_type(
        value: (
            EntityType
            | str
            | None
        ),
    ) -> EntityType | None:

        if isinstance(
            value,
            EntityType,
        ):

            return value

        if value is None:

            return None

        try:

            return EntityType(
                str(
                    value
                )
                .strip()
                .lower()
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

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