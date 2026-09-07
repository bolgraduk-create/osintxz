"""
Image-similarity multimodal analytical adapter.

Phase 6.4.

Normalizes an already-computed ImageSimilarityAnalyzer
comparison result into the shared Phase 6 multimodal
analytical contract.

Pipeline:

existing image hashes A + B
        ↓
ImageSimilarityAnalyzer.compare(...)
        ↓
comparison payload
        ↓
MultimodalImageSimilarityService
        ↓
MultimodalSignalResult(
    kind=IMAGE_SIMILARITY
)

This module does NOT:

- calculate image hashes
- load image files
- execute ImageSimilarityAnalyzer
- query Evidence
- write Evidence metadata
- mark Evidence objects as duplicates
- infer provenance
- infer identity
- create Relationships
- create an artificial confidence score
"""

from __future__ import annotations

from copy import deepcopy

from dataclasses import (
    dataclass,
)

from math import isfinite

from typing import Any

from uuid import UUID

from app.analysis.multimodal_contracts import (
    MultimodalSignalKind,
    MultimodalSignalResult,
    MultimodalSignalScope,
    MultimodalSignalStatus,
)


# ==========================================================
# Normalized comparison details
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class MultimodalImageSimilaritySummary:
    """
    Typed read-only view over the existing
    ImageSimilarityAnalyzer payload.

    This is analytical information only.

    `exact_match` does NOT mean that two Evidence records
    should automatically be merged or deduplicated.
    """

    evidence_id_a: UUID

    evidence_id_b: UUID

    exact_match: bool

    visual_similarity: (
        float
        | None
    )

    classification: (
        str
        | None
    )

    compared_algorithms: int

    perceptual_comparisons: tuple[
        dict[str, Any],
        ...,
    ]

    available_algorithms_a: tuple[
        str,
        ...,
    ]

    available_algorithms_b: tuple[
        str,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.evidence_id_a,
            UUID,
        ):

            raise TypeError(
                "evidence_id_a must be UUID."
            )

        if not isinstance(
            self.evidence_id_b,
            UUID,
        ):

            raise TypeError(
                "evidence_id_b must be UUID."
            )

        if (
            self.evidence_id_a
            ==
            self.evidence_id_b
        ):

            raise ValueError(
                "Image similarity requires two "
                "different Evidence IDs."
            )

        # Canonical pair order.
        canonical = tuple(
            sorted(
                (
                    self.evidence_id_a,
                    self.evidence_id_b,
                ),
                key=str,
            )
        )

        object.__setattr__(
            self,
            "evidence_id_a",
            canonical[
                0
            ],
        )

        object.__setattr__(
            self,
            "evidence_id_b",
            canonical[
                1
            ],
        )

        if not isinstance(
            self.exact_match,
            bool,
        ):

            raise TypeError(
                "exact_match must be bool."
            )

        if (
            self.visual_similarity
            is not None
        ):

            similarity = float(
                self.visual_similarity
            )

            if not isfinite(
                similarity
            ):

                raise ValueError(
                    "visual_similarity must be finite."
                )

            if not (
                0.0
                <=
                similarity
                <=
                1.0
            ):

                raise ValueError(
                    "visual_similarity must be "
                    "between 0 and 1."
                )

            object.__setattr__(
                self,
                "visual_similarity",
                similarity,
            )

        if (
            self.classification
            is not None
        ):

            if not isinstance(
                self.classification,
                str,
            ):

                raise TypeError(
                    "classification must be str or None."
                )

            classification = (
                self.classification
                .strip()
            )

            object.__setattr__(
                self,
                "classification",
                (
                    classification
                    or
                    None
                ),
            )

        if (
            not isinstance(
                self.compared_algorithms,
                int,
            )
            or isinstance(
                self.compared_algorithms,
                bool,
            )
            or self.compared_algorithms < 0
        ):

            raise ValueError(
                "compared_algorithms must be "
                "a non-negative integer."
            )

        if not isinstance(
            self.perceptual_comparisons,
            tuple,
        ):

            raise TypeError(
                "perceptual_comparisons must be tuple."
            )

        normalized_comparisons: list[
            dict[str, Any]
        ] = []

        for comparison in (
            self.perceptual_comparisons
        ):

            if not isinstance(
                comparison,
                dict,
            ):

                raise TypeError(
                    "perceptual_comparisons must "
                    "contain dictionaries."
                )

            normalized_comparisons.append(
                deepcopy(
                    comparison
                )
            )

        object.__setattr__(
            self,
            "perceptual_comparisons",
            tuple(
                normalized_comparisons
            ),
        )

        object.__setattr__(
            self,
            "available_algorithms_a",
            self._normalize_algorithms(
                self.available_algorithms_a,
                name="available_algorithms_a",
            ),
        )

        object.__setattr__(
            self,
            "available_algorithms_b",
            self._normalize_algorithms(
                self.available_algorithms_b,
                name="available_algorithms_b",
            ),
        )

    @staticmethod
    def _normalize_algorithms(
        values: tuple[
            str,
            ...,
        ],
        *,
        name: str,
    ) -> tuple[
        str,
        ...,
    ]:

        if not isinstance(
            values,
            tuple,
        ):

            raise TypeError(
                f"{name} must be tuple."
            )

        normalized: list[
            str
        ] = []

        for value in values:

            if not isinstance(
                value,
                str,
            ):

                raise TypeError(
                    f"{name} must contain strings."
                )

            value = value.strip()

            if value:

                normalized.append(
                    value
                )

        return tuple(
            normalized
        )

    # ==========================================================
    # Pair
    # ==========================================================

    @property
    def evidence_pair(
        self,
    ) -> tuple[
        UUID,
        UUID,
    ]:

        return (
            self.evidence_id_a,
            self.evidence_id_b,
        )


# ==========================================================
# Complete result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class MultimodalImageSimilarityResult:
    """
    Complete Phase 6.4 image-similarity result.

    Preserves both:

    - typed summary
    - generic MultimodalSignalResult
    """

    summary: MultimodalImageSimilaritySummary

    signal: MultimodalSignalResult

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.summary,
            MultimodalImageSimilaritySummary,
        ):

            raise TypeError(
                "summary must be "
                "MultimodalImageSimilaritySummary."
            )

        if not isinstance(
            self.signal,
            MultimodalSignalResult,
        ):

            raise TypeError(
                "signal must be MultimodalSignalResult."
            )

        if (
            self.signal.kind
            !=
            MultimodalSignalKind.IMAGE_SIMILARITY
        ):

            raise ValueError(
                "signal must be IMAGE_SIMILARITY."
            )

        if (
            self.signal.scope
            !=
            MultimodalSignalScope.EVIDENCE_PAIR
        ):

            raise ValueError(
                "Image similarity signal must use "
                "EVIDENCE_PAIR scope."
            )

        if (
            self.signal.status
            !=
            MultimodalSignalStatus.COMPLETED
        ):

            raise ValueError(
                "MultimodalImageSimilarityResult "
                "requires completed signal."
            )

        if (
            self.signal.evidence_pair
            !=
            self.summary.evidence_pair
        ):

            raise ValueError(
                "Similarity summary and signal refer "
                "to different Evidence pairs."
            )

    # ==========================================================
    # Convenience
    # ==========================================================

    @property
    def evidence_pair(
        self,
    ) -> tuple[
        UUID,
        UUID,
    ]:

        return (
            self.summary.evidence_pair
        )

    @property
    def exact_match(
        self,
    ) -> bool:

        return (
            self.summary.exact_match
        )

    @property
    def visual_similarity(
        self,
    ) -> (
        float
        | None
    ):

        return (
            self.summary.visual_similarity
        )

    @property
    def classification(
        self,
    ) -> (
        str
        | None
    ):

        return (
            self.summary.classification
        )


# ==========================================================
# Service
# ==========================================================


class MultimodalImageSimilarityService:
    """
    Pure adapter for already-computed
    ImageSimilarityAnalyzer output.

    Does not own or execute ImageSimilarityAnalyzer.
    """

    SOURCE = (
        "image_similarity_analyzer"
    )

    # ==========================================================
    # Normalize completed comparison
    # ==========================================================

    def adapt(
        self,
        *,
        evidence_id_a: UUID,
        evidence_id_b: UUID,
        comparison: dict[
            str,
            Any,
        ],
    ) -> MultimodalImageSimilarityResult:
        """
        Normalize an existing similarity-comparison payload.
        """

        if not isinstance(
            evidence_id_a,
            UUID,
        ):

            raise TypeError(
                "evidence_id_a must be UUID."
            )

        if not isinstance(
            evidence_id_b,
            UUID,
        ):

            raise TypeError(
                "evidence_id_b must be UUID."
            )

        if (
            evidence_id_a
            ==
            evidence_id_b
        ):

            raise ValueError(
                "Cannot compare Evidence with itself."
            )

        if not isinstance(
            comparison,
            dict,
        ):

            raise TypeError(
                "comparison must be dict."
            )

        # ======================================================
        # Required production fields
        # ======================================================

        if (
            "exact_match"
            not in comparison
        ):

            raise ValueError(
                "Similarity payload is missing "
                "exact_match."
            )

        exact_match = (
            comparison[
                "exact_match"
            ]
        )

        if not isinstance(
            exact_match,
            bool,
        ):

            raise TypeError(
                "exact_match must be bool."
            )

        visual_similarity = (
            comparison.get(
                "visual_similarity"
            )
        )

        classification = (
            comparison.get(
                "classification"
            )
        )

        compared_algorithms = (
            comparison.get(
                "compared_algorithms",
                0,
            )
        )

        raw_comparisons = (
            comparison.get(
                "perceptual_comparisons",
                [],
            )
        )

        if raw_comparisons is None:

            raw_comparisons = []

        if not isinstance(
            raw_comparisons,
            (
                list,
                tuple,
            ),
        ):

            raise TypeError(
                "perceptual_comparisons must "
                "be list or tuple."
            )

        raw_algorithms_a = (
            comparison.get(
                "available_algorithms_a",
                [],
            )
        )

        raw_algorithms_b = (
            comparison.get(
                "available_algorithms_b",
                [],
            )
        )

        if raw_algorithms_a is None:

            raw_algorithms_a = []

        if raw_algorithms_b is None:

            raw_algorithms_b = []

        if not isinstance(
            raw_algorithms_a,
            (
                list,
                tuple,
            ),
        ):

            raise TypeError(
                "available_algorithms_a must "
                "be list or tuple."
            )

        if not isinstance(
            raw_algorithms_b,
            (
                list,
                tuple,
            ),
        ):

            raise TypeError(
                "available_algorithms_b must "
                "be list or tuple."
            )

        # ======================================================
        # Typed summary
        # ======================================================

        summary = (
            MultimodalImageSimilaritySummary(
                evidence_id_a=(
                    evidence_id_a
                ),
                evidence_id_b=(
                    evidence_id_b
                ),
                exact_match=(
                    exact_match
                ),
                visual_similarity=(
                    visual_similarity
                ),
                classification=(
                    classification
                ),
                compared_algorithms=(
                    compared_algorithms
                ),
                perceptual_comparisons=tuple(
                    deepcopy(
                        item
                    )
                    for item
                    in raw_comparisons
                ),
                available_algorithms_a=tuple(
                    str(
                        item
                    )
                    for item
                    in raw_algorithms_a
                ),
                available_algorithms_b=tuple(
                    str(
                        item
                    )
                    for item
                    in raw_algorithms_b
                ),
            )
        )

        # ======================================================
        # Generic Phase 6 signal
        # ======================================================

        signal = (
            MultimodalSignalResult.completed(
                kind=(
                    MultimodalSignalKind
                    .IMAGE_SIMILARITY
                ),
                evidence_ids=(
                    evidence_id_a,
                    evidence_id_b,
                ),
                source=(
                    self.SOURCE
                ),
                data=deepcopy(
                    comparison
                ),
                metadata={
                    "source_contract": (
                        "ImageSimilarityAnalyzer.compare"
                    ),
                    "phase": "6.4",
                },
            )
        )

        return (
            MultimodalImageSimilarityResult(
                summary=summary,
                signal=signal,
            )
        )

    # ==========================================================
    # Unavailable comparison
    # ==========================================================

    def unavailable(
        self,
        *,
        evidence_id_a: UUID,
        evidence_id_b: UUID,
        reason: str,
    ) -> MultimodalSignalResult:
        """
        Represent a comparison that could not be performed.

        No negative similarity conclusion is inferred.
        """

        return (
            MultimodalSignalResult.unavailable(
                kind=(
                    MultimodalSignalKind
                    .IMAGE_SIMILARITY
                ),
                evidence_ids=(
                    evidence_id_a,
                    evidence_id_b,
                ),
                source=(
                    self.SOURCE
                ),
                reason=reason,
                metadata={
                    "source_contract": (
                        "ImageSimilarityAnalyzer.compare"
                    ),
                    "phase": "6.4",
                },
            )
        )

    # ==========================================================
    # Failed comparison
    # ==========================================================

    def failed(
        self,
        *,
        evidence_id_a: UUID,
        evidence_id_b: UUID,
        error: (
            str
            | Exception
        ),
    ) -> MultimodalSignalResult:
        """
        Represent comparison execution failure.
        """

        return (
            MultimodalSignalResult.failed(
                kind=(
                    MultimodalSignalKind
                    .IMAGE_SIMILARITY
                ),
                evidence_ids=(
                    evidence_id_a,
                    evidence_id_b,
                ),
                source=(
                    self.SOURCE
                ),
                error=error,
                metadata={
                    "source_contract": (
                        "ImageSimilarityAnalyzer.compare"
                    ),
                    "phase": "6.4",
                },
            )
        )