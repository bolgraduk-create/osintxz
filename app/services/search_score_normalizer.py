"""
Search score normalization.

Provides reusable normalization strategies for raw
retrieval scores before rank fusion.

Architecture:

Raw retriever scores
        ↓
SearchScoreNormalizer
        ↓
Normalized 0.0-1.0 scores
        ↓
RankFusionService

Responsibilities:

- normalize arbitrary numeric score ranges
- support higher-is-better and lower-is-better metrics
- handle constant score collections safely
- provide deterministic score transformation

Does NOT:

- execute retrieval
- perform rank fusion
- calculate BM25
- calculate cosine similarity
- perform final investigation scoring
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable


class ScoreDirection(str, Enum):
    """
    Defines whether larger or smaller raw values
    represent better retrieval quality.
    """

    HIGHER_IS_BETTER = "higher_is_better"

    LOWER_IS_BETTER = "lower_is_better"


@dataclass(
    frozen=True,
    slots=True,
)
class ScoreRange:
    """
    Observed score range.
    """

    minimum: float

    maximum: float

    @property
    def span(
        self,
    ) -> float:
        """
        Difference between maximum and minimum.
        """

        return (
            self.maximum
            - self.minimum
        )

    @property
    def is_constant(
        self,
    ) -> bool:
        """
        Whether all observed values are equal.
        """

        return (
            self.minimum
            == self.maximum
        )


class SearchScoreNormalizer:
    """
    Normalizes retrieval scores into the common
    0.0-1.0 range.

    This service intentionally contains no assumptions
    about BM25, semantic search or fuzzy search.

    Each retriever may provide raw scores and delegate
    scale conversion here.
    """

    # ==========================================================
    # Public normalization
    # ==========================================================

    def normalize(
        self,
        scores: Iterable[
            float
        ],
        *,
        direction: ScoreDirection = (
            ScoreDirection.HIGHER_IS_BETTER
        ),
    ) -> list[float]:
        """
        Normalize score collection using min-max scaling.

        Higher-is-better:

            minimum -> 0.0
            maximum -> 1.0

        Lower-is-better:

            minimum -> 1.0
            maximum -> 0.0

        Constant collections are mapped to 1.0 because
        all candidates are equally good according to
        this retrieval signal.
        """

        values = [
            self._validate_raw_score(
                value
            )
            for value in scores
        ]

        if not values:

            return []

        score_range = self.get_range(
            values
        )

        if score_range.is_constant:

            return [
                1.0
                for _ in values
            ]

        normalized = [
            self.normalize_value(
                value,
                score_range=score_range,
                direction=direction,
            )
            for value in values
        ]

        return normalized

    def normalize_value(
        self,
        value: float,
        *,
        score_range: ScoreRange,
        direction: ScoreDirection = (
            ScoreDirection.HIGHER_IS_BETTER
        ),
    ) -> float:
        """
        Normalize one value using a known score range.
        """

        numeric_value = (
            self._validate_raw_score(
                value
            )
        )

        minimum = (
            self._validate_raw_score(
                score_range.minimum
            )
        )

        maximum = (
            self._validate_raw_score(
                score_range.maximum
            )
        )

        if maximum < minimum:

            raise ValueError(
                "ScoreRange maximum cannot be "
                "smaller than minimum."
            )

        if maximum == minimum:

            return 1.0

        scaled = (
            numeric_value
            - minimum
        ) / (
            maximum
            - minimum
        )

        # Values outside the observed range are clamped.
        scaled = min(
            1.0,
            max(
                0.0,
                scaled,
            ),
        )

        if (
            direction
            == ScoreDirection.LOWER_IS_BETTER
        ):

            scaled = (
                1.0
                - scaled
            )

        return scaled

    # ==========================================================
    # Range
    # ==========================================================

    def get_range(
        self,
        scores: Iterable[
            float
        ],
    ) -> ScoreRange:
        """
        Calculate score range.
        """

        values = [
            self._validate_raw_score(
                value
            )
            for value in scores
        ]

        if not values:

            raise ValueError(
                "Cannot calculate score range "
                "for an empty collection."
            )

        return ScoreRange(
            minimum=min(
                values
            ),
            maximum=max(
                values
            ),
        )

    # ==========================================================
    # Direct bounded normalization
    # ==========================================================

    def normalize_bounded(
        self,
        value: float,
        *,
        minimum: float,
        maximum: float,
        direction: ScoreDirection = (
            ScoreDirection.HIGHER_IS_BETTER
        ),
    ) -> float:
        """
        Normalize one value when the source metric has a
        predefined numeric range.

        Example:

            percentage:
                0 - 100

            cosine transformed range:
                0 - 1
        """

        return self.normalize_value(
            value,
            score_range=ScoreRange(
                minimum=minimum,
                maximum=maximum,
            ),
            direction=direction,
        )

    # ==========================================================
    # Percentage
    # ==========================================================

    def normalize_percentage(
        self,
        value: float,
    ) -> float:
        """
        Convert a percentage score into 0.0-1.0.

        Examples:

            0      -> 0.0
            50     -> 0.5
            87.5   -> 0.875
            100    -> 1.0
        """

        numeric_value = (
            self._validate_raw_score(
                value
            )
        )

        if not (
            0.0
            <= numeric_value
            <= 100.0
        ):

            raise ValueError(
                "Percentage score must be "
                "between 0 and 100."
            )

        return (
            numeric_value
            / 100.0
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_raw_score(
        value: float,
    ) -> float:
        """
        Validate arbitrary raw numeric score.
        """

        try:

            numeric_value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "Search score must be numeric."
            ) from error

        if not isfinite(
            numeric_value
        ):

            raise ValueError(
                "Search score must be finite."
            )

        return numeric_value