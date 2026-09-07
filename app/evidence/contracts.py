"""
Evidence analysis contracts.

Defines stable domain contracts used by the
Evidence Analysis pipeline.

Responsibilities:

- describe evidence signal direction
- describe evidence signal type
- preserve evidence provenance
- represent one explainable evidence signal
- keep signal strength separate from later
  source reliability and confidence models

Does NOT:

- calculate evidence strength
- calculate source reliability
- calculate corroboration
- calculate source independence
- aggregate final evidence confidence
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


# ==========================================================
# Signal direction
# ==========================================================


class EvidenceSignalDirection(
    str,
    Enum,
):
    """
    Direction of an evidence signal.

    SUPPORT:
        Signal supports the proposition currently
        being evaluated.

    CONTRADICT:
        Signal contradicts the proposition.

    NEUTRAL:
        Signal is relevant context but does not
        directly support either direction.
    """

    SUPPORT = "support"

    CONTRADICT = "contradict"

    NEUTRAL = "neutral"


# ==========================================================
# Signal type
# ==========================================================


class EvidenceSignalType(
    str,
    Enum,
):
    """
    Semantic category of an evidence signal.

    Signal type describes WHAT the signal represents,
    not how trustworthy it is.
    """

    # Evidence integrity / fingerprints.
    INTEGRITY = "integrity"

    # Information extracted from evidence content.
    CONTENT = "content"

    # Relevant structured metadata.
    METADATA = "metadata"

    # Discovery/import/provenance context.
    PROVENANCE = "provenance"

    # Properties of the evidence source.
    SOURCE = "source"

    # Independent evidence supporting the same proposition.
    CORROBORATION = "corroboration"

    # Evidence conflicting with another proposition/evidence.
    CONTRADICTION = "contradiction"

    # Independence/dependence information between sources.
    INDEPENDENCE = "independence"

    # Evidence ↔ Entity association signal.
    ENTITY_LINK = "entity_link"

    # Time-related evidence.
    TEMPORAL = "temporal"

    # Geographic/spatial evidence.
    SPATIAL = "spatial"

    # Future or domain-specific signal.
    OTHER = "other"


# ==========================================================
# Provenance
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceSignalProvenance:
    """
    Provenance of one evidence signal.

    Provenance identifies where the signal came from.

    It is NOT itself a reliability score.

    Example:

        evidence_id
        -> image evidence

        source_id
        -> imported file / Telegram export / OSINT source

        origin
        -> "image_hash_analysis"
    """

    case_id: UUID

    evidence_id: UUID

    source_id: UUID

    evidence_type: str | None = None

    source_type: str | None = None

    origin: str | None = None

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
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            self.source_id,
            UUID,
        ):

            raise TypeError(
                "source_id must be UUID."
            )

        if (
            self.evidence_type
            is not None
            and not str(
                self.evidence_type
            ).strip()
        ):

            raise ValueError(
                "evidence_type cannot be empty."
            )

        if (
            self.source_type
            is not None
            and not str(
                self.source_type
            ).strip()
        ):

            raise ValueError(
                "source_type cannot be empty."
            )

        if (
            self.origin
            is not None
            and not str(
                self.origin
            ).strip()
        ):

            raise ValueError(
                "origin cannot be empty."
            )


# ==========================================================
# Evidence signal
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceSignal:
    """
    One explainable evidence signal.

    strength:
        Intrinsic strength of this signal.

        Range:
            0.0 .. 1.0

        It does NOT include:

        - source reliability
        - corroboration
        - source independence
        - final evidence confidence

    weight:
        Relative importance of this signal inside
        its analytical stage.

        Range:
            0.0 .. 1.0

    weighted_strength:
        strength * weight

    signed_contribution:
        positive for SUPPORT,
        negative for CONTRADICT,
        zero for NEUTRAL.

    Important:

    signed_contribution is an explanatory primitive.

    It is NOT the final Evidence Confidence formula.
    """

    name: str

    signal_type: EvidenceSignalType

    direction: EvidenceSignalDirection

    strength: float

    weight: float = 1.0

    reason: str = ""

    provenance: (
        EvidenceSignalProvenance
        | None
    ) = None

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
                "Evidence signal name "
                "must be a string."
            )

        if not self.name.strip():

            raise ValueError(
                "Evidence signal name "
                "cannot be empty."
            )

        if not isinstance(
            self.signal_type,
            EvidenceSignalType,
        ):

            raise TypeError(
                "signal_type must be an "
                "EvidenceSignalType."
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

        if (
            self.provenance is not None
            and not isinstance(
                self.provenance,
                EvidenceSignalProvenance,
            )
        ):

            raise TypeError(
                "provenance must be an "
                "EvidenceSignalProvenance."
            )

        if not isinstance(
            self.details,
            dict,
        ):

            raise TypeError(
                "details must be a dictionary."
            )

    # ==========================================================
    # Properties
    # ==========================================================

    @property
    def weighted_strength(
        self,
    ) -> float:
        """
        Weighted signal strength.

        Because both inputs are bounded to 0..1,
        result is also bounded to 0..1.
        """

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
    def signed_contribution(
        self,
    ) -> float:
        """
        Direction-aware weighted strength.
        """

        if (
            self.direction
            ==
            EvidenceSignalDirection.SUPPORT
        ):

            return (
                self.weighted_strength
            )

        if (
            self.direction
            ==
            EvidenceSignalDirection.CONTRADICT
        ):

            return (
                -self.weighted_strength
            )

        return 0.0

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

    # ==========================================================
    # Validation
    # ==========================================================

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
# Signal collection
# ==========================================================


@dataclass(
    slots=True,
)
class EvidenceSignalCollection:
    """
    Collection of signals produced for one Evidence object.

    This is a transport/domain contract only.

    No scoring is performed here.
    """

    case_id: UUID

    evidence_id: UUID

    source_id: UUID

    signals: list[
        EvidenceSignal
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.evidence_id,
            UUID,
        ):

            raise TypeError(
                "evidence_id must be UUID."
            )

        if not isinstance(
            self.source_id,
            UUID,
        ):

            raise TypeError(
                "source_id must be UUID."
            )

        if not isinstance(
            self.signals,
            list,
        ):

            raise TypeError(
                "signals must be a list."
            )

        for signal in self.signals:

            if not isinstance(
                signal,
                EvidenceSignal,
            ):

                raise TypeError(
                    "signals must contain only "
                    "EvidenceSignal objects."
                )

    # ==========================================================
    # Signal manipulation
    # ==========================================================

    def add_signal(
        self,
        signal: EvidenceSignal,
    ) -> None:

        if not isinstance(
            signal,
            EvidenceSignal,
        ):

            raise TypeError(
                "signal must be an "
                "EvidenceSignal."
            )

        self.signals.append(
            signal
        )

    # ==========================================================
    # Views
    # ==========================================================

    @property
    def supporting_signals(
        self,
    ) -> tuple[
        EvidenceSignal,
        ...,
    ]:

        return tuple(
            signal
            for signal
            in self.signals
            if signal.is_support
        )

    @property
    def contradicting_signals(
        self,
    ) -> tuple[
        EvidenceSignal,
        ...,
    ]:

        return tuple(
            signal
            for signal
            in self.signals
            if signal.is_contradiction
        )

    @property
    def neutral_signals(
        self,
    ) -> tuple[
        EvidenceSignal,
        ...,
    ]:

        return tuple(
            signal
            for signal
            in self.signals
            if signal.is_neutral
        )

    @property
    def has_support(
        self,
    ) -> bool:

        return bool(
            self.supporting_signals
        )

    @property
    def has_contradiction(
        self,
    ) -> bool:

        return bool(
            self.contradicting_signals
        )