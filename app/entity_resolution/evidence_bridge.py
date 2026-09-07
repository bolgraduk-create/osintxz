"""
Evidence -> Entity Resolution bridge.

Converts explicit Evidence-based identity observations
into conservative EntityResolutionSignal objects.

Responsibilities:

- bind Evidence to one concrete entity pair
- require explicit identity direction
- combine Entity <-> Evidence association results
- optionally apply directional Evidence Confidence
- preserve discovery-path provenance
- prevent Evidence-only identity certainty
- collapse correlated Evidence observations
- produce standard EntityResolutionSignal objects

Does NOT:

- automatically infer identity from shared Evidence
- execute Entity Resolution
- make MATCH / NO_MATCH decisions
- create EntityMerge records
- modify EvidenceEntity links
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from math import isfinite

from typing import Any

from uuid import UUID

from app.entity_resolution.contracts import (
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
    EntityResolutionSignalType,
)

from app.evidence.discovery_path import (
    DiscoveryPath,
)

from app.evidence.entity_evidence_scoring import (
    EntityEvidenceAssociationResult,
)

from app.evidence.evidence_confidence import (
    EvidenceConfidenceBreakdown,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceIdentityBridgeConfig:
    """
    Conservative Evidence -> Identity weights.

    These values are deliberately below the normal
    single-signal automatic identity thresholds.

    Evidence therefore participates in Entity
    Resolution, but cannot become identity certainty
    on its own.
    """

    support_weight: float = 0.80

    contradiction_weight: float = 0.80

    def __post_init__(
        self,
    ) -> None:

        self._validate_weight(
            self.support_weight,
            field_name="support_weight",
        )

        self._validate_weight(
            self.contradiction_weight,
            field_name=(
                "contradiction_weight"
            ),
        )

    @staticmethod
    def _validate_weight(
        value: float,
        *,
        field_name: str,
    ) -> None:

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
                f"{field_name} must be between "
                "0.0 and 1.0."
            )


# ==========================================================
# Observation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceIdentityBridgeObservation:
    """
    One explicit Evidence-based identity observation.

    Important:

    The caller explicitly chooses direction.

    Merely observing that the same Evidence object is
    associated with two Entities is NOT sufficient to
    create identity support automatically.

    proposition_key:

        Stable identity proposition describing what
        the Evidence Confidence result refers to.

    Example:

        "entity_identity:<id-a>:<id-b>"
    """

    proposition_key: str

    first_association: (
        EntityEvidenceAssociationResult
    )

    second_association: (
        EntityEvidenceAssociationResult
    )

    direction: (
        EntityResolutionSignalDirection
    )

    identity_relevance: float = 1.0

    evidence_confidence: (
        EvidenceConfidenceBreakdown
        | None
    ) = None

    discovery_path: (
        DiscoveryPath
        | None
    ) = None

    reason: str = ""

    details: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        proposition_key = str(
            self.proposition_key
        ).strip()

        if not proposition_key:

            raise ValueError(
                "proposition_key cannot "
                "be empty."
            )

        object.__setattr__(
            self,
            "proposition_key",
            proposition_key,
        )

        if not isinstance(
            self.first_association,
            EntityEvidenceAssociationResult,
        ):

            raise TypeError(
                "first_association must be an "
                "EntityEvidenceAssociationResult."
            )

        if not isinstance(
            self.second_association,
            EntityEvidenceAssociationResult,
        ):

            raise TypeError(
                "second_association must be an "
                "EntityEvidenceAssociationResult."
            )

        if not isinstance(
            self.direction,
            EntityResolutionSignalDirection,
        ):

            raise TypeError(
                "direction must be an "
                "EntityResolutionSignalDirection."
            )

        relevance = float(
            self.identity_relevance
        )

        if (
            not isfinite(
                relevance
            )
            or not (
                0.0
                <= relevance
                <= 1.0
            )
        ):

            raise ValueError(
                "identity_relevance must be "
                "between 0.0 and 1.0."
            )

        object.__setattr__(
            self,
            "identity_relevance",
            relevance,
        )

        first = (
            self.first_association
        )

        second = (
            self.second_association
        )

        # ======================================================
        # Case binding
        # ======================================================

        if (
            first.case_id
            !=
            second.case_id
        ):

            raise ValueError(
                "Evidence identity bridge cannot "
                "cross investigation cases."
            )

        # ======================================================
        # Evidence binding
        #
        # One observation describes how ONE Evidence
        # object relates to both Entities.
        # ======================================================

        if (
            first.evidence_id
            !=
            second.evidence_id
        ):

            raise ValueError(
                "Both associations must belong "
                "to the same Evidence object."
            )

        # ======================================================
        # Entity pair
        # ======================================================

        if (
            first.entity_id
            ==
            second.entity_id
        ):

            raise ValueError(
                "Evidence identity bridge requires "
                "two different Entities."
            )

        # ======================================================
        # Evidence Confidence binding
        # ======================================================

        if (
            self.evidence_confidence
            is not None
        ):

            if not isinstance(
                self.evidence_confidence,
                EvidenceConfidenceBreakdown,
            ):

                raise TypeError(
                    "evidence_confidence must be an "
                    "EvidenceConfidenceBreakdown "
                    "or None."
                )

            if (
                self.evidence_confidence
                .proposition_key
                !=
                proposition_key
            ):

                raise ValueError(
                    "Evidence Confidence belongs "
                    "to a different proposition."
                )

        # ======================================================
        # Discovery path binding
        # ======================================================

        if (
            self.discovery_path
            is not None
        ):

            if not isinstance(
                self.discovery_path,
                DiscoveryPath,
            ):

                raise TypeError(
                    "discovery_path must be a "
                    "DiscoveryPath or None."
                )

            if (
                self.discovery_path.case_id
                !=
                first.case_id
            ):

                raise ValueError(
                    "Discovery path belongs to "
                    "a different investigation case."
                )

        if not isinstance(
            self.reason,
            str,
        ):

            raise TypeError(
                "reason must be a string."
            )

        object.__setattr__(
            self,
            "reason",
            self.reason.strip(),
        )

        if not isinstance(
            self.details,
            dict,
        ):

            raise TypeError(
                "details must be a dictionary."
            )

        object.__setattr__(
            self,
            "details",
            dict(
                self.details
            ),
        )

    # ==========================================================
    # Pair identity
    # ==========================================================

    @property
    def case_id(
        self,
    ) -> UUID:

        return (
            self.first_association
            .case_id
        )

    @property
    def evidence_id(
        self,
    ) -> UUID:

        return (
            self.first_association
            .evidence_id
        )

    @property
    def first_entity_id(
        self,
    ) -> UUID:

        return (
            self.first_association
            .entity_id
        )

    @property
    def second_entity_id(
        self,
    ) -> UUID:

        return (
            self.second_association
            .entity_id
        )

    @property
    def canonical_entity_ids(
        self,
    ) -> tuple[
        UUID,
        UUID,
    ]:

        return tuple(
            sorted(
                (
                    self.first_entity_id,
                    self.second_entity_id,
                ),
                key=str,
            )
        )

    # ==========================================================
    # Association components
    # ==========================================================

    @property
    def first_positive_strength(
        self,
    ) -> float:

        return self._clamp(
            self.first_association
            .association_score
            *
            self.first_association
            .confidence
        )

    @property
    def second_positive_strength(
        self,
    ) -> float:

        return self._clamp(
            self.second_association
            .association_score
            *
            self.second_association
            .confidence
        )

    @property
    def first_negative_strength(
        self,
    ) -> float:

        return self._clamp(
            self.first_association
            .contradiction_score
            *
            self.first_association
            .confidence
        )

    @property
    def second_negative_strength(
        self,
    ) -> float:

        return self._clamp(
            self.second_association
            .contradiction_score
            *
            self.second_association
            .confidence
        )

    # ==========================================================
    # Raw directional strength
    # ==========================================================

    @property
    def raw_support_strength(
        self,
    ) -> float:
        """
        Both sides must be positively associated with
        the same Evidence object.
        """

        return min(
            self.first_positive_strength,
            self.second_positive_strength,
        )

    @property
    def raw_contradiction_strength(
        self,
    ) -> float:
        """
        Contradiction requires asymmetric Evidence:

        Evidence strongly associates with Entity A
        while contradicting Entity B,

        or vice versa.
        """

        first_to_second_conflict = min(
            self.first_positive_strength,
            self.second_negative_strength,
        )

        second_to_first_conflict = min(
            self.second_positive_strength,
            self.first_negative_strength,
        )

        return max(
            first_to_second_conflict,
            second_to_first_conflict,
        )

    # ==========================================================
    # Directional Evidence Confidence
    # ==========================================================

    @property
    def evidence_gate(
        self,
    ) -> float:
        """
        Direction-aware Evidence Confidence factor.

        SUPPORT:
            use final proposition confidence.

        CONTRADICT:
            use contradiction strength from the
            Evidence Confidence model.

        NEUTRAL:
            zero.

        Missing Evidence Confidence is not treated as
        negative. Association results still provide
        the bridge evidence.
        """

        if (
            self.direction
            ==
            EntityResolutionSignalDirection.NEUTRAL
        ):

            return 0.0

        if (
            self.evidence_confidence
            is None
        ):

            return 1.0

        if (
            self.direction
            ==
            EntityResolutionSignalDirection.SUPPORT
        ):

            return self._clamp(
                self.evidence_confidence
                .confidence_score
            )

        return self._clamp(
            max(
                self.evidence_confidence
                .contradiction_strength,
                self.evidence_confidence
                .conflict_score,
            )
        )

    # ==========================================================
    # Final observation strength
    # ==========================================================

    @property
    def bridge_strength(
        self,
    ) -> float:

        if (
            self.direction
            ==
            EntityResolutionSignalDirection.SUPPORT
        ):

            raw_strength = (
                self.raw_support_strength
            )

        elif (
            self.direction
            ==
            EntityResolutionSignalDirection
            .CONTRADICT
        ):

            raw_strength = (
                self.raw_contradiction_strength
            )

        else:

            return 0.0

        return self._clamp(
            raw_strength
            *
            self.identity_relevance
            *
            self.evidence_gate
        )

    # ==========================================================
    # Stable identity
    # ==========================================================

    @property
    def identity_key(
        self,
    ) -> tuple[
        str,
        str,
        str,
        str,
    ]:

        first_id, second_id = (
            self.canonical_entity_ids
        )

        return (
            str(
                first_id
            ),
            str(
                second_id
            ),
            str(
                self.evidence_id
            ),
            self.direction.value,
        )

    # ==========================================================
    # Helper
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


# ==========================================================
# Bridge result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceIdentityBridgeResult:
    """
    Explainable result of converting Evidence
    observations to identity signals.

    At most:

        one SUPPORT signal
        one CONTRADICT signal

    are produced.

    This prevents multiple correlated Evidence objects
    from being mistaken for independent identity
    signals.
    """

    signals: tuple[
        EntityResolutionSignal,
        ...,
    ]

    input_observation_count: int

    unique_observation_count: int

    duplicate_observation_count: int

    supporting_observation_count: int

    contradicting_observation_count: int

    neutral_observation_count: int

    strongest_support_evidence_id: (
        UUID
        | None
    ) = None

    strongest_contradiction_evidence_id: (
        UUID
        | None
    ) = None

    @property
    def has_support(
        self,
    ) -> bool:

        return any(
            signal.direction
            ==
            EntityResolutionSignalDirection.SUPPORT
            for signal
            in self.signals
        )

    @property
    def has_contradiction(
        self,
    ) -> bool:

        return any(
            signal.direction
            ==
            EntityResolutionSignalDirection
            .CONTRADICT
            for signal
            in self.signals
        )


# ==========================================================
# Service
# ==========================================================


class EvidenceIdentityBridgeService:
    """
    Convert Evidence identity observations into standard
    Entity Resolution signals.

    Correlation safety:

        many Evidence observations
            ↓
        strongest SUPPORT observation
        +
        strongest CONTRADICT observation

    Evidence observations therefore cannot inflate
    identity score merely by count.
    """

    def __init__(
        self,
        config: (
            EvidenceIdentityBridgeConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or EvidenceIdentityBridgeConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        observations: list[
            EvidenceIdentityBridgeObservation
        ],
    ) -> EvidenceIdentityBridgeResult:
        """
        Convert Evidence observations into resolution
        signals.

        No database writes are performed.
        """

        if not isinstance(
            observations,
            list,
        ):

            raise TypeError(
                "observations must be a list."
            )

        input_count = len(
            observations
        )

        (
            unique_observations,
            duplicate_count,
        ) = self._deduplicate(
            observations
        )

        supporting = [
            observation
            for observation
            in unique_observations
            if (
                observation.direction
                ==
                EntityResolutionSignalDirection.SUPPORT
                and
                observation.bridge_strength
                >
                0.0
            )
        ]

        contradicting = [
            observation
            for observation
            in unique_observations
            if (
                observation.direction
                ==
                EntityResolutionSignalDirection
                .CONTRADICT
                and
                observation.bridge_strength
                >
                0.0
            )
        ]

        neutral_count = sum(
            1
            for observation
            in unique_observations
            if (
                observation.direction
                ==
                EntityResolutionSignalDirection.NEUTRAL
            )
        )

        signals: list[
            EntityResolutionSignal
        ] = []

        strongest_support = (
            self._strongest(
                supporting
            )
        )

        strongest_contradiction = (
            self._strongest(
                contradicting
            )
        )

        if strongest_support is not None:

            signals.append(
                self._build_signal(
                    strongest_support,
                    direction=(
                        EntityResolutionSignalDirection
                        .SUPPORT
                    ),
                    weight=(
                        self.config
                        .support_weight
                    ),
                )
            )

        if (
            strongest_contradiction
            is not None
        ):

            signals.append(
                self._build_signal(
                    strongest_contradiction,
                    direction=(
                        EntityResolutionSignalDirection
                        .CONTRADICT
                    ),
                    weight=(
                        self.config
                        .contradiction_weight
                    ),
                )
            )

        signals.sort(
            key=lambda signal: (
                signal.direction.value,
                signal.name,
            )
        )

        return (
            EvidenceIdentityBridgeResult(
                signals=tuple(
                    signals
                ),
                input_observation_count=(
                    input_count
                ),
                unique_observation_count=(
                    len(
                        unique_observations
                    )
                ),
                duplicate_observation_count=(
                    duplicate_count
                ),
                supporting_observation_count=(
                    len(
                        supporting
                    )
                ),
                contradicting_observation_count=(
                    len(
                        contradicting
                    )
                ),
                neutral_observation_count=(
                    neutral_count
                ),
                strongest_support_evidence_id=(
                    strongest_support
                    .evidence_id
                    if (
                        strongest_support
                        is not None
                    )
                    else None
                ),
                strongest_contradiction_evidence_id=(
                    strongest_contradiction
                    .evidence_id
                    if (
                        strongest_contradiction
                        is not None
                    )
                    else None
                ),
            )
        )

    # ==========================================================
    # Signal construction
    # ==========================================================

    @staticmethod
    def _build_signal(
        observation: (
            EvidenceIdentityBridgeObservation
        ),
        *,
        direction: (
            EntityResolutionSignalDirection
        ),
        weight: float,
    ) -> EntityResolutionSignal:

        first_id, second_id = (
            observation
            .canonical_entity_ids
        )

        discovery_chain: tuple[
            str,
            ...,
        ] = ()

        discovery_depth: (
            int
            | None
        ) = None

        discovery_tools: tuple[
            str,
            ...,
        ] = ()

        if (
            observation.discovery_path
            is not None
        ):

            discovery_chain = (
                observation.discovery_path
                .explainable_chain
            )

            discovery_depth = (
                observation.discovery_path
                .depth
            )

            discovery_tools = (
                observation.discovery_path
                .tools_used
            )

        reason = (
            observation.reason
            or (
                "Evidence provides additional "
                "identity support."
                if (
                    direction
                    ==
                    EntityResolutionSignalDirection
                    .SUPPORT
                )
                else (
                    "Evidence provides additional "
                    "identity contradiction."
                )
            )
        )

        return (
            EntityResolutionSignal(
                name=(
                    "evidence_identity_support"
                    if (
                        direction
                        ==
                        EntityResolutionSignalDirection
                        .SUPPORT
                    )
                    else (
                        "evidence_identity_"
                        "contradiction"
                    )
                ),
                signal_type=(
                    EntityResolutionSignalType
                    .EVIDENCE
                ),
                direction=direction,
                score=(
                    observation
                    .bridge_strength
                ),
                weight=weight,
                reason=reason,
                details={
                    "evidence_bridge": True,

                    "case_id": str(
                        observation.case_id
                    ),

                    "entity_pair": (
                        str(
                            first_id
                        ),
                        str(
                            second_id
                        ),
                    ),

                    "evidence_id": str(
                        observation.evidence_id
                    ),

                    "proposition_key": (
                        observation
                        .proposition_key
                    ),

                    "identity_relevance": (
                        observation
                        .identity_relevance
                    ),

                    "first_association_score": (
                        observation
                        .first_association
                        .association_score
                    ),

                    "first_association_confidence": (
                        observation
                        .first_association
                        .confidence
                    ),

                    "first_association_"
                    "contradiction": (
                        observation
                        .first_association
                        .contradiction_score
                    ),

                    "second_association_score": (
                        observation
                        .second_association
                        .association_score
                    ),

                    "second_association_confidence": (
                        observation
                        .second_association
                        .confidence
                    ),

                    "second_association_"
                    "contradiction": (
                        observation
                        .second_association
                        .contradiction_score
                    ),

                    "raw_support_strength": (
                        observation
                        .raw_support_strength
                    ),

                    "raw_contradiction_strength": (
                        observation
                        .raw_contradiction_strength
                    ),

                    "evidence_gate": (
                        observation
                        .evidence_gate
                    ),

                    "bridge_strength": (
                        observation
                        .bridge_strength
                    ),

                    "discovery_depth": (
                        discovery_depth
                    ),

                    "discovery_tools": (
                        discovery_tools
                    ),

                    "discovery_chain": (
                        discovery_chain
                    ),

                    **dict(
                        observation.details
                    ),
                },
            )
        )

    # ==========================================================
    # Deduplication
    # ==========================================================

    @staticmethod
    def _deduplicate(
        observations: list[
            EvidenceIdentityBridgeObservation
        ],
    ) -> tuple[
        list[
            EvidenceIdentityBridgeObservation
        ],
        int,
    ]:

        unique: dict[
            tuple[
                str,
                str,
                str,
                str,
            ],
            EvidenceIdentityBridgeObservation,
        ] = {}

        duplicate_count = 0

        for observation in observations:

            if not isinstance(
                observation,
                EvidenceIdentityBridgeObservation,
            ):

                raise TypeError(
                    "observations must contain only "
                    "EvidenceIdentityBridgeObservation "
                    "objects."
                )

            key = (
                observation.identity_key
            )

            existing = unique.get(
                key
            )

            if existing is None:

                unique[
                    key
                ] = observation

                continue

            duplicate_count += 1

            if (
                observation.bridge_strength
                >
                existing.bridge_strength
            ):

                unique[
                    key
                ] = observation

                continue

            if (
                observation.bridge_strength
                ==
                existing.bridge_strength
                and
                EvidenceIdentityBridgeService
                ._stable_observation_key(
                    observation
                )
                <
                EvidenceIdentityBridgeService
                ._stable_observation_key(
                    existing
                )
            ):

                unique[
                    key
                ] = observation

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
    # Strongest observation
    # ==========================================================

    @staticmethod
    def _strongest(
        observations: list[
            EvidenceIdentityBridgeObservation
        ],
    ) -> (
        EvidenceIdentityBridgeObservation
        | None
    ):

        if not observations:

            return None

        return max(
            observations,
            key=lambda observation: (
                observation.bridge_strength,
                EvidenceIdentityBridgeService
                ._stable_observation_key(
                    observation
                ),
            ),
        )

    # ==========================================================
    # Determinism
    # ==========================================================

    @staticmethod
    def _stable_observation_key(
        observation: (
            EvidenceIdentityBridgeObservation
        ),
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
    ]:

        first_id, second_id = (
            observation
            .canonical_entity_ids
        )

        return (
            str(
                first_id
            ),
            str(
                second_id
            ),
            str(
                observation.evidence_id
            ),
            observation.direction.value,
            observation.reason,
        )