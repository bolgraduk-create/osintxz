"""
Source reliability analysis.

Evaluates observable technical properties of a Source.

Responsibilities:

- assess source integrity indicators
- assess provenance completeness
- assess import / processing state
- detect checksum and size inconsistencies
- keep missing information separate from negative evidence
- expose reliability and coverage separately
- provide explainable factor breakdown

Does NOT:

- judge truthfulness of source content
- rank source types such as Telegram / PDF / OSINT
- calculate evidence corroboration
- calculate source independence
- calculate final evidence confidence
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from enum import Enum

import json
import math
import re

from typing import (
    Any,
)


# ==========================================================
# Factor state
# ==========================================================


class SourceReliabilityFactorState(
    str,
    Enum,
):
    """
    State of one reliability factor.

    POSITIVE:
        Factor was evaluated and fully supports
        technical source reliability.

    PARTIAL:
        Factor was evaluated but only partially
        supports reliability.

    NEGATIVE:
        Factor was evaluated and indicates a
        technical inconsistency or failure.

    UNKNOWN:
        Factor cannot currently be evaluated.

    UNKNOWN is intentionally different from NEGATIVE.
    Missing metadata must not automatically mean
    unreliable source.
    """

    POSITIVE = "positive"

    PARTIAL = "partial"

    NEGATIVE = "negative"

    UNKNOWN = "unknown"


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SourceReliabilityConfig:
    """
    Reliability factor weights.

    Weights describe the relative analytical importance
    of observable technical source properties.

    They are NOT probabilities.
    """

    checksum_presence_weight: float = 0.15

    original_path_weight: float = 0.10

    size_presence_weight: float = 0.05

    provenance_metadata_weight: float = 0.15

    source_status_weight: float = 0.15

    checksum_consistency_weight: float = 0.20

    size_consistency_weight: float = 0.10

    processing_status_weight: float = 0.10

    provenance_metadata_keys: tuple[
        str,
        ...,
    ] = (
        "import_kind",
        "imported_at",
        "original_name",
        "stored_name",
        "stored_path",
    )

    successful_source_statuses: frozenset[
        str
    ] = frozenset(
        {
            "imported",
            "ready",
        }
    )

    failed_source_statuses: frozenset[
        str
    ] = frozenset(
        {
            "failed",
        }
    )

    unresolved_source_statuses: frozenset[
        str
    ] = frozenset(
        {
            "pending",
            "importing",
        }
    )

    successful_processing_statuses: frozenset[
        str
    ] = frozenset(
        {
            "completed",
            "complete",
            "success",
            "successful",
            "ready",
        }
    )

    failed_processing_statuses: frozenset[
        str
    ] = frozenset(
        {
            "failed",
            "error",
            "errored",
        }
    )

    unresolved_processing_statuses: frozenset[
        str
    ] = frozenset(
        {
            "pending",
            "processing",
            "importing",
            "running",
        }
    )

    def __post_init__(
        self,
    ) -> None:

        for (
            name,
            weight,
        ) in self.factor_weights.items():

            numeric_weight = float(
                weight
            )

            if (
                not math.isfinite(
                    numeric_weight
                )
                or numeric_weight < 0.0
            ):

                raise ValueError(
                    f"{name} must be a finite "
                    "non-negative weight."
                )

        if self.total_weight <= 0.0:

            raise ValueError(
                "Source reliability total weight "
                "must be positive."
            )

    @property
    def factor_weights(
        self,
    ) -> dict[
        str,
        float,
    ]:

        return {
            "checksum_presence": (
                self.checksum_presence_weight
            ),
            "original_path": (
                self.original_path_weight
            ),
            "size_presence": (
                self.size_presence_weight
            ),
            "provenance_metadata": (
                self.provenance_metadata_weight
            ),
            "source_status": (
                self.source_status_weight
            ),
            "checksum_consistency": (
                self.checksum_consistency_weight
            ),
            "size_consistency": (
                self.size_consistency_weight
            ),
            "processing_status": (
                self.processing_status_weight
            ),
        }

    @property
    def total_weight(
        self,
    ) -> float:

        return sum(
            self.factor_weights.values()
        )


# ==========================================================
# Factor
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SourceReliabilityFactor:
    """
    One observable source-reliability factor.

    quality:
        0.0 .. 1.0 when evaluated.

        None when the factor is UNKNOWN.

    weight:
        Relative factor importance.

    weighted_quality:
        quality * weight for evaluated factors.
    """

    name: str

    state: SourceReliabilityFactorState

    quality: float | None

    weight: float

    reason: str

    details: dict[
        str,
        Any,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not self.name.strip():

            raise ValueError(
                "Reliability factor name "
                "cannot be empty."
            )

        if not isinstance(
            self.state,
            SourceReliabilityFactorState,
        ):

            raise TypeError(
                "state must be a "
                "SourceReliabilityFactorState."
            )

        if (
            self.quality is None
        ):

            if (
                self.state
                !=
                SourceReliabilityFactorState
                .UNKNOWN
            ):

                raise ValueError(
                    "Only UNKNOWN factors may "
                    "have quality=None."
                )

        else:

            quality = float(
                self.quality
            )

            if (
                not math.isfinite(
                    quality
                )
                or not (
                    0.0
                    <= quality
                    <= 1.0
                )
            ):

                raise ValueError(
                    "Factor quality must be "
                    "between 0.0 and 1.0."
                )

        weight = float(
            self.weight
        )

        if (
            not math.isfinite(
                weight
            )
            or weight < 0.0
        ):

            raise ValueError(
                "Factor weight must be a finite "
                "non-negative number."
            )

    @property
    def is_evaluated(
        self,
    ) -> bool:

        return (
            self.quality
            is not None
        )

    @property
    def weighted_quality(
        self,
    ) -> float:

        if self.quality is None:

            return 0.0

        return (
            float(
                self.quality
            )
            *
            float(
                self.weight
            )
        )


# ==========================================================
# Breakdown
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SourceReliabilityBreakdown:
    """
    Explainable Source Reliability result.

    reliability_score:
        Weighted quality of evaluated factors only.

        Missing information does NOT directly lower
        this score.

    coverage_score:
        Fraction of the configured reliability model
        that could actually be evaluated.

    Example:

        one valid original_path only:

            reliability_score = 1.0
            coverage_score    = 0.10

    Therefore reliability_score must never be confused
    with final evidence confidence.
    """

    reliability_score: float

    coverage_score: float

    evaluated_weight: float

    total_weight: float

    factors: tuple[
        SourceReliabilityFactor,
        ...,
    ]

    evaluated_factor_count: int

    positive_factor_count: int

    partial_factor_count: int

    negative_factor_count: int

    unknown_factor_count: int

    invalid_metadata: bool = False

    @property
    def has_evaluated_factors(
        self,
    ) -> bool:

        return (
            self.evaluated_factor_count
            >
            0
        )

    @property
    def negative_factors(
        self,
    ) -> tuple[
        SourceReliabilityFactor,
        ...,
    ]:

        return tuple(
            factor
            for factor
            in self.factors
            if (
                factor.state
                ==
                SourceReliabilityFactorState
                .NEGATIVE
            )
        )

    @property
    def unknown_factors(
        self,
    ) -> tuple[
        SourceReliabilityFactor,
        ...,
    ]:

        return tuple(
            factor
            for factor
            in self.factors
            if (
                factor.state
                ==
                SourceReliabilityFactorState
                .UNKNOWN
            )
        )


# ==========================================================
# Service
# ==========================================================


class SourceReliabilityScoringService:
    """
    Evaluate observable technical reliability
    properties of one Source.

    Important:

    source_type is deliberately NOT used as a score.

    A Telegram source is not automatically better or
    worse than a file, API, PDF or OSINT source.
    """

    _SHA256_PATTERN = re.compile(
        r"^[0-9a-fA-F]{64}$"
    )

    def __init__(
        self,
        config: (
            SourceReliabilityConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or SourceReliabilityConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def score(
        self,
        source: Any,
    ) -> SourceReliabilityBreakdown:
        """
        Calculate technical Source Reliability.

        The object only needs to expose Source-like
        attributes. No database access is performed.
        """

        metadata, invalid_metadata = (
            self._parse_metadata(
                getattr(
                    source,
                    "metadata_json",
                    None,
                )
            )
        )

        factors = (
            self._build_factors(
                source=source,
                metadata=metadata,
                invalid_metadata=(
                    invalid_metadata
                ),
            )
        )

        evaluated = [
            factor
            for factor
            in factors
            if factor.is_evaluated
        ]

        evaluated_weight = sum(
            factor.weight
            for factor
            in evaluated
        )

        weighted_quality = sum(
            factor.weighted_quality
            for factor
            in evaluated
        )

        if evaluated_weight <= 0.0:

            reliability_score = 0.0

        else:

            reliability_score = (
                weighted_quality
                /
                evaluated_weight
            )

        coverage_score = (
            evaluated_weight
            /
            self.config.total_weight
        )

        reliability_score = (
            self._clamp(
                reliability_score
            )
        )

        coverage_score = (
            self._clamp(
                coverage_score
            )
        )

        return (
            SourceReliabilityBreakdown(
                reliability_score=(
                    reliability_score
                ),
                coverage_score=(
                    coverage_score
                ),
                evaluated_weight=(
                    evaluated_weight
                ),
                total_weight=(
                    self.config.total_weight
                ),
                factors=tuple(
                    factors
                ),
                evaluated_factor_count=(
                    len(
                        evaluated
                    )
                ),
                positive_factor_count=(
                    self._count_state(
                        factors,
                        SourceReliabilityFactorState
                        .POSITIVE,
                    )
                ),
                partial_factor_count=(
                    self._count_state(
                        factors,
                        SourceReliabilityFactorState
                        .PARTIAL,
                    )
                ),
                negative_factor_count=(
                    self._count_state(
                        factors,
                        SourceReliabilityFactorState
                        .NEGATIVE,
                    )
                ),
                unknown_factor_count=(
                    self._count_state(
                        factors,
                        SourceReliabilityFactorState
                        .UNKNOWN,
                    )
                ),
                invalid_metadata=(
                    invalid_metadata
                ),
            )
        )

    # ==========================================================
    # Factors
    # ==========================================================

    def _build_factors(
        self,
        *,
        source: Any,
        metadata: dict[str, Any] | None,
        invalid_metadata: bool,
    ) -> list[
        SourceReliabilityFactor
    ]:

        return [
            self._checksum_presence_factor(
                source
            ),

            self._original_path_factor(
                source
            ),

            self._size_presence_factor(
                source
            ),

            self._provenance_metadata_factor(
                metadata=metadata,
                invalid_metadata=(
                    invalid_metadata
                ),
            ),

            self._source_status_factor(
                source
            ),

            self._checksum_consistency_factor(
                source=source,
                metadata=metadata,
            ),

            self._size_consistency_factor(
                source=source,
                metadata=metadata,
            ),

            self._processing_status_factor(
                metadata
            ),
        ]

    # ==========================================================
    # Checksum presence
    # ==========================================================

    def _checksum_presence_factor(
        self,
        source: Any,
    ) -> SourceReliabilityFactor:

        checksum = self._text(
            getattr(
                source,
                "checksum",
                None,
            )
        )

        if not checksum:

            return self._unknown_factor(
                name="checksum_presence",
                weight=(
                    self.config
                    .checksum_presence_weight
                ),
                reason=(
                    "No source checksum is "
                    "currently available."
                ),
            )

        return self._quality_factor(
            name="checksum_presence",
            quality=1.0,
            weight=(
                self.config
                .checksum_presence_weight
            ),
            reason=(
                "Source has an integrity "
                "fingerprint."
            ),
            details={
                "checksum_present": True,
            },
        )

    # ==========================================================
    # Original path
    # ==========================================================

    def _original_path_factor(
        self,
        source: Any,
    ) -> SourceReliabilityFactor:

        original_path = self._text(
            getattr(
                source,
                "original_path",
                None,
            )
        )

        if not original_path:

            return self._unknown_factor(
                name="original_path",
                weight=(
                    self.config
                    .original_path_weight
                ),
                reason=(
                    "Original source location "
                    "is not recorded."
                ),
            )

        return self._quality_factor(
            name="original_path",
            quality=1.0,
            weight=(
                self.config
                .original_path_weight
            ),
            reason=(
                "Original source location "
                "is recorded."
            ),
            details={
                "original_path_present": True,
            },
        )

    # ==========================================================
    # Size
    # ==========================================================

    def _size_presence_factor(
        self,
        source: Any,
    ) -> SourceReliabilityFactor:

        raw_size = getattr(
            source,
            "size_bytes",
            None,
        )

        if raw_size is None:

            return self._unknown_factor(
                name="size_presence",
                weight=(
                    self.config
                    .size_presence_weight
                ),
                reason=(
                    "Source size is not recorded."
                ),
            )

        size = self._non_negative_int(
            raw_size
        )

        if size is None:

            return self._quality_factor(
                name="size_presence",
                quality=0.0,
                weight=(
                    self.config
                    .size_presence_weight
                ),
                reason=(
                    "Recorded source size "
                    "is invalid."
                ),
                details={
                    "raw_size": repr(
                        raw_size
                    ),
                },
            )

        return self._quality_factor(
            name="size_presence",
            quality=1.0,
            weight=(
                self.config
                .size_presence_weight
            ),
            reason=(
                "Source size is recorded."
            ),
            details={
                "size_bytes": size,
            },
        )

    # ==========================================================
    # Provenance metadata
    # ==========================================================

    def _provenance_metadata_factor(
        self,
        *,
        metadata: dict[
            str,
            Any,
        ] | None,
        invalid_metadata: bool,
    ) -> SourceReliabilityFactor:

        if metadata is None:

            reason = (
                "Source metadata could not "
                "be parsed."
                if invalid_metadata
                else
                "No structured provenance "
                "metadata is available."
            )

            return self._unknown_factor(
                name="provenance_metadata",
                weight=(
                    self.config
                    .provenance_metadata_weight
                ),
                reason=reason,
                details={
                    "invalid_metadata": (
                        invalid_metadata
                    ),
                },
            )

        keys = (
            self.config
            .provenance_metadata_keys
        )

        present_keys = [
            key
            for key
            in keys
            if self._has_value(
                metadata.get(
                    key
                )
            )
        ]

        if not present_keys:

            return self._unknown_factor(
                name="provenance_metadata",
                weight=(
                    self.config
                    .provenance_metadata_weight
                ),
                reason=(
                    "No recognized provenance "
                    "metadata fields are available."
                ),
            )

        completeness = (
            len(
                present_keys
            )
            /
            len(
                keys
            )
        )

        return self._quality_factor(
            name="provenance_metadata",
            quality=completeness,
            weight=(
                self.config
                .provenance_metadata_weight
            ),
            reason=(
                "Structured source provenance "
                "metadata is available."
            ),
            details={
                "present_keys": (
                    sorted(
                        present_keys
                    )
                ),
                "expected_keys": list(
                    keys
                ),
                "completeness": (
                    completeness
                ),
            },
        )

    # ==========================================================
    # Source status
    # ==========================================================

    def _source_status_factor(
        self,
        source: Any,
    ) -> SourceReliabilityFactor:

        status = self._enum_text(
            getattr(
                source,
                "status",
                None,
            )
        )

        if not status:

            return self._unknown_factor(
                name="source_status",
                weight=(
                    self.config
                    .source_status_weight
                ),
                reason=(
                    "Source status is unavailable."
                ),
            )

        if (
            status
            in
            self.config
            .successful_source_statuses
        ):

            return self._quality_factor(
                name="source_status",
                quality=1.0,
                weight=(
                    self.config
                    .source_status_weight
                ),
                reason=(
                    "Source import state indicates "
                    "successful availability."
                ),
                details={
                    "status": status,
                },
            )

        if (
            status
            in
            self.config
            .failed_source_statuses
        ):

            return self._quality_factor(
                name="source_status",
                quality=0.0,
                weight=(
                    self.config
                    .source_status_weight
                ),
                reason=(
                    "Source import state indicates "
                    "failure."
                ),
                details={
                    "status": status,
                },
            )

        # PENDING / IMPORTING are known states,
        # but do not yet provide reliability evidence.
        return self._unknown_factor(
            name="source_status",
            weight=(
                self.config
                .source_status_weight
            ),
            reason=(
                "Source processing state is not "
                "yet conclusive for reliability."
            ),
            details={
                "status": status,
            },
        )

    # ==========================================================
    # Checksum consistency
    # ==========================================================

    def _checksum_consistency_factor(
        self,
        *,
        source: Any,
        metadata: dict[
            str,
            Any,
        ] | None,
    ) -> SourceReliabilityFactor:

        source_checksum = self._text(
            getattr(
                source,
                "checksum",
                None,
            )
        ).lower()

        metadata_sha256 = ""

        if metadata is not None:

            metadata_sha256 = self._text(
                metadata.get(
                    "sha256"
                )
            ).lower()

        # We compare only when both values are
        # clearly SHA-256 fingerprints.
        if not (
            self._is_sha256(
                source_checksum
            )
            and
            self._is_sha256(
                metadata_sha256
            )
        ):

            return self._unknown_factor(
                name="checksum_consistency",
                weight=(
                    self.config
                    .checksum_consistency_weight
                ),
                reason=(
                    "Checksum consistency cannot "
                    "currently be evaluated."
                ),
            )

        matches = (
            source_checksum
            ==
            metadata_sha256
        )

        return self._quality_factor(
            name="checksum_consistency",
            quality=(
                1.0
                if matches
                else 0.0
            ),
            weight=(
                self.config
                .checksum_consistency_weight
            ),
            reason=(
                "Source checksum matches "
                "import metadata."
                if matches
                else
                "Source checksum conflicts "
                "with import metadata."
            ),
            details={
                "matches": matches,
            },
        )

    # ==========================================================
    # Size consistency
    # ==========================================================

    def _size_consistency_factor(
        self,
        *,
        source: Any,
        metadata: dict[
            str,
            Any,
        ] | None,
    ) -> SourceReliabilityFactor:

        source_size = (
            self._non_negative_int(
                getattr(
                    source,
                    "size_bytes",
                    None,
                )
            )
        )

        metadata_size = None

        if metadata is not None:

            metadata_size = (
                self._non_negative_int(
                    metadata.get(
                        "size_bytes"
                    )
                )
            )

        if (
            source_size is None
            or metadata_size is None
        ):

            return self._unknown_factor(
                name="size_consistency",
                weight=(
                    self.config
                    .size_consistency_weight
                ),
                reason=(
                    "Source size consistency cannot "
                    "currently be evaluated."
                ),
            )

        matches = (
            source_size
            ==
            metadata_size
        )

        return self._quality_factor(
            name="size_consistency",
            quality=(
                1.0
                if matches
                else 0.0
            ),
            weight=(
                self.config
                .size_consistency_weight
            ),
            reason=(
                "Source size matches "
                "import metadata."
                if matches
                else
                "Source size conflicts "
                "with import metadata."
            ),
            details={
                "source_size": source_size,
                "metadata_size": (
                    metadata_size
                ),
                "matches": matches,
            },
        )

    # ==========================================================
    # Processing
    # ==========================================================

    def _processing_status_factor(
        self,
        metadata: dict[
            str,
            Any,
        ] | None,
    ) -> SourceReliabilityFactor:

        if metadata is None:

            return self._unknown_factor(
                name="processing_status",
                weight=(
                    self.config
                    .processing_status_weight
                ),
                reason=(
                    "Processing metadata "
                    "is unavailable."
                ),
            )

        processing = metadata.get(
            "processing"
        )

        if not isinstance(
            processing,
            dict,
        ):

            return self._unknown_factor(
                name="processing_status",
                weight=(
                    self.config
                    .processing_status_weight
                ),
                reason=(
                    "Structured processing state "
                    "is unavailable."
                ),
            )

        status = self._text(
            processing.get(
                "status"
            )
        ).lower()

        errors = processing.get(
            "errors"
        )

        error_count = (
            len(
                errors
            )
            if isinstance(
                errors,
                list,
            )
            else 0
        )

        if (
            status
            in
            self.config
            .successful_processing_statuses
        ):

            quality = (
                1.0
                if error_count == 0
                else 0.5
            )

            return self._quality_factor(
                name="processing_status",
                quality=quality,
                weight=(
                    self.config
                    .processing_status_weight
                ),
                reason=(
                    "Source processing completed "
                    "successfully."
                    if error_count == 0
                    else
                    "Source processing completed "
                    "with recorded errors."
                ),
                details={
                    "status": status,
                    "error_count": (
                        error_count
                    ),
                },
            )

        if (
            status
            in
            self.config
            .failed_processing_statuses
        ):

            return self._quality_factor(
                name="processing_status",
                quality=0.0,
                weight=(
                    self.config
                    .processing_status_weight
                ),
                reason=(
                    "Source processing failed."
                ),
                details={
                    "status": status,
                    "error_count": (
                        error_count
                    ),
                },
            )

        return self._unknown_factor(
            name="processing_status",
            weight=(
                self.config
                .processing_status_weight
            ),
            reason=(
                "Source processing state is not "
                "conclusive for reliability."
            ),
            details={
                "status": status,
                "error_count": (
                    error_count
                ),
            },
        )

    # ==========================================================
    # Factor constructors
    # ==========================================================

    @staticmethod
    def _quality_factor(
        *,
        name: str,
        quality: float,
        weight: float,
        reason: str,
        details: dict[
            str,
            Any,
        ] | None = None,
    ) -> SourceReliabilityFactor:

        quality = (
            SourceReliabilityScoringService
            ._clamp(
                quality
            )
        )

        if quality >= 1.0:

            state = (
                SourceReliabilityFactorState
                .POSITIVE
            )

        elif quality <= 0.0:

            state = (
                SourceReliabilityFactorState
                .NEGATIVE
            )

        else:

            state = (
                SourceReliabilityFactorState
                .PARTIAL
            )

        return SourceReliabilityFactor(
            name=name,
            state=state,
            quality=quality,
            weight=weight,
            reason=reason,
            details=(
                dict(
                    details
                    or {}
                )
            ),
        )

    @staticmethod
    def _unknown_factor(
        *,
        name: str,
        weight: float,
        reason: str,
        details: dict[
            str,
            Any,
        ] | None = None,
    ) -> SourceReliabilityFactor:

        return SourceReliabilityFactor(
            name=name,
            state=(
                SourceReliabilityFactorState
                .UNKNOWN
            ),
            quality=None,
            weight=weight,
            reason=reason,
            details=(
                dict(
                    details
                    or {}
                )
            ),
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    @staticmethod
    def _parse_metadata(
        raw_metadata: Any,
    ) -> tuple[
        dict[str, Any] | None,
        bool,
    ]:

        if raw_metadata is None:

            return (
                None,
                False,
            )

        if isinstance(
            raw_metadata,
            dict,
        ):

            return (
                raw_metadata,
                False,
            )

        text = str(
            raw_metadata
        ).strip()

        if not text:

            return (
                None,
                False,
            )

        try:

            decoded = json.loads(
                text
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            return (
                None,
                True,
            )

        if not isinstance(
            decoded,
            dict,
        ):

            return (
                None,
                True,
            )

        return (
            decoded,
            False,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @classmethod
    def _is_sha256(
        cls,
        value: str,
    ) -> bool:

        return bool(
            cls._SHA256_PATTERN.fullmatch(
                value
            )
        )

    @staticmethod
    def _enum_text(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        raw_value = getattr(
            value,
            "value",
            value,
        )

        return str(
            raw_value
        ).strip().lower()

    @staticmethod
    def _text(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        ).strip()

    @staticmethod
    def _has_value(
        value: Any,
    ) -> bool:

        if value is None:

            return False

        if isinstance(
            value,
            str,
        ):

            return bool(
                value.strip()
            )

        return True

    @staticmethod
    def _non_negative_int(
        value: Any,
    ) -> int | None:

        if value is None:

            return None

        if isinstance(
            value,
            bool,
        ):

            return None

        try:

            numeric = int(
                value
            )

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):

            return None

        if numeric < 0:

            return None

        return numeric

    @staticmethod
    def _count_state(
        factors: list[
            SourceReliabilityFactor
        ],
        state: (
            SourceReliabilityFactorState
        ),
    ) -> int:

        return sum(
            1
            for factor
            in factors
            if factor.state == state
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