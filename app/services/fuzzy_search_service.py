"""
Fuzzy string similarity service.

Provides mathematical string similarity methods used by
the Unified Investigation Search Engine.

Implemented methods:

- normalized Levenshtein similarity
- Jaro similarity
- Jaro-Winkler similarity
- trigram Jaccard similarity
- combined fuzzy similarity

Architecture:

raw strings
    ↓
FuzzySearchService
    ↓
normalized similarity signals
    ↓
FuzzySearchRetriever
    ↓
UnifiedSearchService
    ↓
RRF

Responsibilities:

- normalize textual values
- calculate edit-distance similarity
- calculate Jaro / Jaro-Winkler similarity
- calculate trigram similarity
- combine several fuzzy signals
- return normalized scores in range 0.0-1.0

Does NOT:

- access database
- search SearchIndex directly
- perform rank fusion
- perform semantic search
- perform entity resolution
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
import unicodedata


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class FuzzySearchConfig:
    """
    Configuration for combined fuzzy similarity.

    The three similarity algorithms capture different
    properties:

    Levenshtein:
        character edit distance

    Jaro-Winkler:
        short strings, names and small typos

    Trigram:
        overlapping character sequences
    """

    levenshtein_weight: float = 0.35

    jaro_winkler_weight: float = 0.45

    trigram_weight: float = 0.20

    jaro_winkler_prefix_scale: float = 0.1

    jaro_winkler_max_prefix: int = 4

    def __post_init__(
        self,
    ) -> None:

        weights = (
            self.levenshtein_weight,
            self.jaro_winkler_weight,
            self.trigram_weight,
        )

        for weight in weights:

            if not isfinite(
                weight
            ):

                raise ValueError(
                    "Fuzzy search weights "
                    "must be finite."
                )

            if weight < 0.0:

                raise ValueError(
                    "Fuzzy search weights "
                    "cannot be negative."
                )

        if sum(
            weights
        ) <= 0.0:

            raise ValueError(
                "At least one fuzzy search "
                "weight must be greater than zero."
            )

        if not (
            0.0
            <= self.jaro_winkler_prefix_scale
            <= 0.25
        ):

            raise ValueError(
                "Jaro-Winkler prefix scale must "
                "be between 0.0 and 0.25."
            )

        if (
            self.jaro_winkler_max_prefix
            < 0
        ):

            raise ValueError(
                "Jaro-Winkler max prefix "
                "cannot be negative."
            )


# ==========================================================
# Result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class FuzzySimilarityResult:
    """
    Detailed fuzzy comparison result.
    """

    combined: float

    levenshtein: float

    jaro_winkler: float

    trigram: float

    normalized_left: str

    normalized_right: str

    @property
    def exact(
        self,
    ) -> bool:
        """
        Whether normalized strings are identical.
        """

        return (
            self.normalized_left
            == self.normalized_right
            and bool(
                self.normalized_left
            )
        )


# ==========================================================
# Service
# ==========================================================


class FuzzySearchService:
    """
    Mathematical fuzzy string similarity service.
    """

    def __init__(
        self,
        config: FuzzySearchConfig | None = None,
    ) -> None:

        self.config = (
            config
            or FuzzySearchConfig()
        )

    # ======================================================
    # Main comparison
    # ======================================================

    def compare(
        self,
        left: str,
        right: str,
    ) -> FuzzySimilarityResult:
        """
        Compare two strings using all configured
        fuzzy similarity methods.
        """

        normalized_left = self.normalize(
            left
        )

        normalized_right = self.normalize(
            right
        )

        # --------------------------------------------------
        # Empty strings
        # --------------------------------------------------

        if (
            not normalized_left
            or not normalized_right
        ):

            return FuzzySimilarityResult(
                combined=0.0,
                levenshtein=0.0,
                jaro_winkler=0.0,
                trigram=0.0,
                normalized_left=(
                    normalized_left
                ),
                normalized_right=(
                    normalized_right
                ),
            )

        # --------------------------------------------------
        # Exact equality
        # --------------------------------------------------

        if (
            normalized_left
            == normalized_right
        ):

            return FuzzySimilarityResult(
                combined=1.0,
                levenshtein=1.0,
                jaro_winkler=1.0,
                trigram=1.0,
                normalized_left=(
                    normalized_left
                ),
                normalized_right=(
                    normalized_right
                ),
            )

        # --------------------------------------------------
        # Independent signals
        # --------------------------------------------------

        levenshtein_score = (
            self.levenshtein_similarity(
                normalized_left,
                normalized_right,
                normalize_input=False,
            )
        )

        jaro_winkler_score = (
            self.jaro_winkler_similarity(
                normalized_left,
                normalized_right,
                normalize_input=False,
            )
        )

        trigram_score = (
            self.trigram_similarity(
                normalized_left,
                normalized_right,
                normalize_input=False,
            )
        )

        # --------------------------------------------------
        # Weighted combination
        # --------------------------------------------------

        total_weight = (
            self.config.levenshtein_weight
            + self.config.jaro_winkler_weight
            + self.config.trigram_weight
        )

        combined = (
            (
                levenshtein_score
                * self.config.levenshtein_weight
            )
            + (
                jaro_winkler_score
                * self.config.jaro_winkler_weight
            )
            + (
                trigram_score
                * self.config.trigram_weight
            )
        ) / total_weight

        combined = self._clamp(
            combined
        )

        return FuzzySimilarityResult(
            combined=combined,
            levenshtein=levenshtein_score,
            jaro_winkler=(
                jaro_winkler_score
            ),
            trigram=trigram_score,
            normalized_left=(
                normalized_left
            ),
            normalized_right=(
                normalized_right
            ),
        )

    # ======================================================
    # Normalization
    # ======================================================

    def normalize(
        self,
        value: str | None,
    ) -> str:
        """
        Normalize value before fuzzy comparison.

        Operations:

        - convert to string
        - Unicode normalization
        - case folding
        - collapse whitespace
        - trim surrounding whitespace

        Punctuation is intentionally preserved.

        This is important for investigation data such as:

            john@example.com
            user_name
            example-domain.com

        where punctuation carries meaning.
        """

        if value is None:

            return ""

        text = str(
            value
        )

        text = unicodedata.normalize(
            "NFKC",
            text,
        )

        text = text.casefold()

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ======================================================
    # Levenshtein
    # ======================================================

    def levenshtein_distance(
        self,
        left: str,
        right: str,
        *,
        normalize_input: bool = True,
    ) -> int:
        """
        Calculate classic Levenshtein edit distance.

        Distance represents the minimum number of:

        - insertions
        - deletions
        - substitutions

        required to transform one string into another.
        """

        if normalize_input:

            left = self.normalize(
                left
            )

            right = self.normalize(
                right
            )

        if left == right:

            return 0

        if not left:

            return len(
                right
            )

        if not right:

            return len(
                left
            )

        # Keep the shorter string in the column dimension
        # to reduce memory usage from O(n*m) to O(min(n,m)).

        if len(
            left
        ) < len(
            right
        ):

            shorter = left

            longer = right

        else:

            shorter = right

            longer = left

        previous_row = list(
            range(
                len(
                    shorter
                )
                + 1
            )
        )

        for row_index, longer_char in enumerate(
            longer,
            start=1,
        ):

            current_row = [
                row_index
            ]

            for (
                column_index,
                shorter_char,
            ) in enumerate(
                shorter,
                start=1,
            ):

                insertion = (
                    current_row[
                        column_index
                        - 1
                    ]
                    + 1
                )

                deletion = (
                    previous_row[
                        column_index
                    ]
                    + 1
                )

                substitution = (
                    previous_row[
                        column_index
                        - 1
                    ]
                    + (
                        0
                        if longer_char
                        == shorter_char
                        else 1
                    )
                )

                current_row.append(
                    min(
                        insertion,
                        deletion,
                        substitution,
                    )
                )

            previous_row = (
                current_row
            )

        return previous_row[
            -1
        ]

    def levenshtein_similarity(
        self,
        left: str,
        right: str,
        *,
        normalize_input: bool = True,
    ) -> float:
        """
        Convert Levenshtein distance into similarity:

            similarity =
                1 - distance / max_length
        """

        if normalize_input:

            left = self.normalize(
                left
            )

            right = self.normalize(
                right
            )

        if left == right:

            return (
                1.0
                if left
                else 0.0
            )

        maximum_length = max(
            len(
                left
            ),
            len(
                right
            ),
        )

        if maximum_length == 0:

            return 0.0

        distance = (
            self.levenshtein_distance(
                left,
                right,
                normalize_input=False,
            )
        )

        similarity = (
            1.0
            - (
                distance
                / maximum_length
            )
        )

        return self._clamp(
            similarity
        )

    # ======================================================
    # Jaro
    # ======================================================

    def jaro_similarity(
        self,
        left: str,
        right: str,
        *,
        normalize_input: bool = True,
    ) -> float:
        """
        Calculate Jaro similarity.

        Jaro is particularly useful for short strings,
        names and small character transpositions.
        """

        if normalize_input:

            left = self.normalize(
                left
            )

            right = self.normalize(
                right
            )

        if left == right:

            return (
                1.0
                if left
                else 0.0
            )

        if (
            not left
            or not right
        ):

            return 0.0

        left_length = len(
            left
        )

        right_length = len(
            right
        )

        match_distance = max(
            left_length,
            right_length,
        ) // 2 - 1

        match_distance = max(
            0,
            match_distance,
        )

        left_matches = [
            False
        ] * left_length

        right_matches = [
            False
        ] * right_length

        matches = 0

        # --------------------------------------------------
        # Matching characters
        # --------------------------------------------------

        for left_index in range(
            left_length
        ):

            start = max(
                0,
                left_index
                - match_distance,
            )

            end = min(
                left_index
                + match_distance
                + 1,
                right_length,
            )

            for right_index in range(
                start,
                end,
            ):

                if right_matches[
                    right_index
                ]:

                    continue

                if (
                    left[
                        left_index
                    ]
                    != right[
                        right_index
                    ]
                ):

                    continue

                left_matches[
                    left_index
                ] = True

                right_matches[
                    right_index
                ] = True

                matches += 1

                break

        if matches == 0:

            return 0.0

        # --------------------------------------------------
        # Transpositions
        # --------------------------------------------------

        matched_left = [
            left[index]
            for index in range(
                left_length
            )
            if left_matches[
                index
            ]
        ]

        matched_right = [
            right[index]
            for index in range(
                right_length
            )
            if right_matches[
                index
            ]
        ]

        transpositions = sum(
            left_char
            != right_char
            for (
                left_char,
                right_char,
            ) in zip(
                matched_left,
                matched_right,
            )
        ) / 2.0

        similarity = (
            (
                matches
                / left_length
            )
            + (
                matches
                / right_length
            )
            + (
                (
                    matches
                    - transpositions
                )
                / matches
            )
        ) / 3.0

        return self._clamp(
            similarity
        )

    # ======================================================
    # Jaro-Winkler
    # ======================================================

    def jaro_winkler_similarity(
        self,
        left: str,
        right: str,
        *,
        normalize_input: bool = True,
    ) -> float:
        """
        Calculate Jaro-Winkler similarity.

        Jaro-Winkler increases similarity when both
        strings share the same prefix.

        This is especially useful for names:

            Alexander
            Aleksander

            Petrov
            Petroff
        """

        if normalize_input:

            left = self.normalize(
                left
            )

            right = self.normalize(
                right
            )

        jaro = self.jaro_similarity(
            left,
            right,
            normalize_input=False,
        )

        if jaro <= 0.0:

            return 0.0

        prefix_length = 0

        maximum_prefix = min(
            self.config
            .jaro_winkler_max_prefix,
            len(
                left
            ),
            len(
                right
            ),
        )

        for index in range(
            maximum_prefix
        ):

            if (
                left[
                    index
                ]
                != right[
                    index
                ]
            ):

                break

            prefix_length += 1

        similarity = (
            jaro
            + (
                prefix_length
                * self.config
                .jaro_winkler_prefix_scale
                * (
                    1.0
                    - jaro
                )
            )
        )

        return self._clamp(
            similarity
        )

    # ======================================================
    # Trigrams
    # ======================================================

    def trigram_similarity(
        self,
        left: str,
        right: str,
        *,
        normalize_input: bool = True,
    ) -> float:
        """
        Calculate trigram Jaccard similarity.

        Strings are transformed into overlapping
        3-character sequences.

        Example:

            PETROV

        becomes approximately:

            PET
            ETR
            TRO
            ROV

        Similarity is then:

            |A ∩ B|
            -------
            |A ∪ B|
        """

        if normalize_input:

            left = self.normalize(
                left
            )

            right = self.normalize(
                right
            )

        if left == right:

            return (
                1.0
                if left
                else 0.0
            )

        if (
            not left
            or not right
        ):

            return 0.0

        left_grams = (
            self._ngrams(
                left,
                size=3,
            )
        )

        right_grams = (
            self._ngrams(
                right,
                size=3,
            )
        )

        union = (
            left_grams
            | right_grams
        )

        if not union:

            return 0.0

        intersection = (
            left_grams
            & right_grams
        )

        similarity = (
            len(
                intersection
            )
            / len(
                union
            )
        )

        return self._clamp(
            similarity
        )

    # ======================================================
    # N-grams
    # ======================================================

    @staticmethod
    def _ngrams(
        value: str,
        *,
        size: int,
    ) -> set[str]:
        """
        Build character n-grams.

        Short strings are kept as one complete gram
        instead of producing an empty set.
        """

        if size < 1:

            raise ValueError(
                "N-gram size must "
                "be at least 1."
            )

        if not value:

            return set()

        if len(
            value
        ) <= size:

            return {
                value
            }

        return {
            value[
                index:
                index + size
            ]
            for index in range(
                len(
                    value
                )
                - size
                + 1
            )
        }

    # ======================================================
    # Helpers
    # ======================================================

    @staticmethod
    def _clamp(
        value: float,
    ) -> float:
        """
        Clamp floating point similarity to 0.0-1.0.
        """

        return min(
            1.0,
            max(
                0.0,
                float(
                    value
                ),
            ),
        )