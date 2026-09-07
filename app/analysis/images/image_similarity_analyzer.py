"""
Image similarity analyzer.

Compares image hash fingerprints and produces
a normalized similarity assessment.

Architecture:

Image hash result A
        +
Image hash result B
        ↓
ImageSimilarityAnalyzer
        ↓
Hash distances
        ↓
Similarity scores
        ↓
Unified comparison result

Responsibilities:

- detect exact file matches
- compare perceptual hashes
- calculate Hamming distances
- normalize distances into similarity scores
- combine multiple perceptual algorithms
- classify overall similarity

Does NOT:

- access the database
- load evidence records
- modify files
- search an investigation
- interact with desktop widgets
- calculate hashes from image files
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
)

from typing import Any


@dataclass(
    slots=True,
    frozen=True,
)
class HashComparison:
    """
    Result of one hash comparison.
    """

    algorithm: str

    hash_a: str
    hash_b: str

    distance: int

    bits: int

    similarity: float

    identical: bool

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Serialize comparison.
        """

        return {
            "algorithm": self.algorithm,
            "hash_a": self.hash_a,
            "hash_b": self.hash_b,
            "distance": self.distance,
            "bits": self.bits,
            "similarity": self.similarity,
            "identical": self.identical,
        }


class ImageSimilarityAnalyzer:
    """
    Compare previously calculated image hashes.

    Cryptographic hashes identify exact file matches.

    Perceptual hashes estimate visual similarity.
    """

    name = "similarity"

    description = (
        "Compare image fingerprints and estimate "
        "visual similarity."
    )

    version = "1.0"

    # ==========================================================
    # Algorithms
    # ==========================================================

    CRYPTOGRAPHIC_HASHES = (
        "sha256",
        "sha512",
        "sha1",
        "md5",
    )

    PERCEPTUAL_HASHES = (
        "perceptual_hash",
        "difference_hash",
        "average_hash",
        "wavelet_hash",
    )

    HASH_ALIASES = {
        "perceptual_hash": (
            "perceptual_hash",
            "phash",
            "p_hash",
        ),
        "difference_hash": (
            "difference_hash",
            "dhash",
            "d_hash",
        ),
        "average_hash": (
            "average_hash",
            "ahash",
            "a_hash",
        ),
        "wavelet_hash": (
            "wavelet_hash",
            "whash",
            "w_hash",
        ),
        "color_hash": (
            "color_hash",
            "colorhash",
        ),
        "sha256": (
            "sha256",
            "sha_256",
        ),
        "sha512": (
            "sha512",
            "sha_512",
        ),
        "sha1": (
            "sha1",
            "sha_1",
        ),
        "md5": (
            "md5",
        ),
    }

    DEFAULT_WEIGHTS = {
        "perceptual_hash": 0.40,
        "difference_hash": 0.25,
        "average_hash": 0.15,
        "wavelet_hash": 0.20,
    }

    # ==========================================================
    # Main API
    # ==========================================================

    def compare(
        self,
        hashes_a: dict[str, Any],
        hashes_b: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compare two sets of image hashes.
        """

        normalized_a = self._normalize_hashes(
            hashes_a
        )

        normalized_b = self._normalize_hashes(
            hashes_b
        )

        exact_match = self._exact_match(
            normalized_a,
            normalized_b,
        )

        perceptual = (
            self._compare_perceptual_hashes(
                normalized_a,
                normalized_b,
            )
        )

        overall_similarity = (
            self._calculate_overall_similarity(
                perceptual
            )
        )

        if exact_match:

            overall_similarity = 100.0

        classification = (
            self._classify(
                similarity=overall_similarity,
                exact_match=exact_match,
                comparisons=len(
                    perceptual
                ),
            )
        )

        return {
            "exact_match": exact_match,
            "visual_similarity": (
                overall_similarity
            ),
            "classification": (
                classification
            ),
            "perceptual_comparisons": {
                name: comparison.to_dict()
                for name, comparison
                in perceptual.items()
            },
            "compared_algorithms": list(
                perceptual.keys()
            ),
            "available_algorithms_a": (
                self._available_algorithms(
                    normalized_a
                )
            ),
            "available_algorithms_b": (
                self._available_algorithms(
                    normalized_b
                )
            ),
        }

    # ==========================================================
    # Exact matching
    # ==========================================================

    def _exact_match(
        self,
        hashes_a: dict[str, str],
        hashes_b: dict[str, str],
    ) -> bool:
        """
        Detect byte-identical files.

        The strongest available shared cryptographic
        hash is used.
        """

        for algorithm in (
            self.CRYPTOGRAPHIC_HASHES
        ):

            hash_a = hashes_a.get(
                algorithm
            )

            hash_b = hashes_b.get(
                algorithm
            )

            if (
                hash_a
                and hash_b
            ):

                return (
                    hash_a.lower()
                    ==
                    hash_b.lower()
                )

        return False

    # ==========================================================
    # Perceptual comparison
    # ==========================================================

    def _compare_perceptual_hashes(
        self,
        hashes_a: dict[str, str],
        hashes_b: dict[str, str],
    ) -> dict[
        str,
        HashComparison,
    ]:
        """
        Compare all shared perceptual hashes.
        """

        comparisons: dict[
            str,
            HashComparison,
        ] = {}

        for algorithm in (
            self.PERCEPTUAL_HASHES
        ):

            hash_a = hashes_a.get(
                algorithm
            )

            hash_b = hashes_b.get(
                algorithm
            )

            if (
                not hash_a
                or not hash_b
            ):

                continue

            comparison = (
                self._compare_hex_hash(
                    algorithm=algorithm,
                    hash_a=hash_a,
                    hash_b=hash_b,
                )
            )

            if comparison is not None:

                comparisons[
                    algorithm
                ] = comparison

        return comparisons

    @staticmethod
    def _compare_hex_hash(
        *,
        algorithm: str,
        hash_a: str,
        hash_b: str,
    ) -> HashComparison | None:
        """
        Compare two hexadecimal perceptual hashes.
        """

        normalized_a = (
            str(
                hash_a
            )
            .strip()
            .lower()
        )

        normalized_b = (
            str(
                hash_b
            )
            .strip()
            .lower()
        )

        if (
            not normalized_a
            or not normalized_b
        ):

            return None

        if (
            len(
                normalized_a
            )
            !=
            len(
                normalized_b
            )
        ):

            return None

        try:

            integer_a = int(
                normalized_a,
                16,
            )

            integer_b = int(
                normalized_b,
                16,
            )

        except ValueError:

            return None

        bits = (
            len(
                normalized_a
            )
            * 4
        )

        if bits <= 0:

            return None

        distance = (
            integer_a
            ^
            integer_b
        ).bit_count()

        similarity = (
            1.0
            -
            (
                distance
                /
                bits
            )
        ) * 100.0

        similarity = max(
            0.0,
            min(
                100.0,
                similarity,
            ),
        )

        return HashComparison(
            algorithm=algorithm,
            hash_a=normalized_a,
            hash_b=normalized_b,
            distance=distance,
            bits=bits,
            similarity=round(
                similarity,
                2,
            ),
            identical=(
                distance == 0
            ),
        )

    # ==========================================================
    # Overall score
    # ==========================================================

    def _calculate_overall_similarity(
        self,
        comparisons: dict[
            str,
            HashComparison,
        ],
    ) -> float | None:
        """
        Calculate weighted visual similarity.

        Missing algorithms are ignored and remaining
        weights are normalized automatically.
        """

        if not comparisons:

            return None

        weighted_score = 0.0

        total_weight = 0.0

        for algorithm, comparison in (
            comparisons.items()
        ):

            weight = (
                self.DEFAULT_WEIGHTS.get(
                    algorithm,
                    1.0,
                )
            )

            weighted_score += (
                comparison.similarity
                *
                weight
            )

            total_weight += weight

        if total_weight <= 0:

            return None

        return round(
            weighted_score
            /
            total_weight,
            2,
        )

    # ==========================================================
    # Classification
    # ==========================================================

    @staticmethod
    def _classify(
        *,
        similarity: float | None,
        exact_match: bool,
        comparisons: int,
    ) -> str:
        """
        Convert score into a human-readable category.

        These categories are heuristic indicators,
        not forensic conclusions.
        """

        if exact_match:

            return "exact"

        if (
            similarity is None
            or comparisons == 0
        ):

            return "insufficient_data"

        if similarity >= 95.0:

            return "very_high"

        if similarity >= 85.0:

            return "high"

        if similarity >= 70.0:

            return "moderate"

        if similarity >= 50.0:

            return "low"

        return "very_low"

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_hashes(
        self,
        hashes: dict[str, Any],
    ) -> dict[str, str]:
        """
        Normalize different hash-result structures.

        Supports:

        {
            "sha256": "...",
            "perceptual_hash": "..."
        }

        and:

        {
            "cryptographic": {...},
            "perceptual": {...}
        }

        and complete analyzer results:

        {
            "data": {...}
        }
        """

        if not isinstance(
            hashes,
            dict,
        ):

            raise TypeError(
                "Image hashes must be a dictionary."
            )

        source = hashes

        data = source.get(
            "data"
        )

        if isinstance(
            data,
            dict,
        ):

            source = data

        candidates: dict[
            str,
            Any,
        ] = {}

        candidates.update(
            source
        )

        cryptographic = source.get(
            "cryptographic"
        )

        if isinstance(
            cryptographic,
            dict,
        ):

            candidates.update(
                cryptographic
            )

        perceptual = source.get(
            "perceptual"
        )

        if isinstance(
            perceptual,
            dict,
        ):

            candidates.update(
                perceptual
            )

        normalized_candidates = {
            str(
                key
            ).strip().lower(): value
            for key, value
            in candidates.items()
        }

        normalized: dict[
            str,
            str,
        ] = {}

        for canonical_name, aliases in (
            self.HASH_ALIASES.items()
        ):

            for alias in aliases:

                value = (
                    normalized_candidates.get(
                        alias.lower()
                    )
                )

                if value is None:

                    continue

                text = str(
                    value
                ).strip()

                if not text:

                    continue

                normalized[
                    canonical_name
                ] = text

                break

        return normalized

    # ==========================================================
    # Information
    # ==========================================================

    def _available_algorithms(
        self,
        hashes: dict[str, str],
    ) -> list[str]:
        """
        Return available recognized algorithms.
        """

        order = (
            *self.CRYPTOGRAPHIC_HASHES,
            *self.PERCEPTUAL_HASHES,
            "color_hash",
        )

        return [
            algorithm
            for algorithm
            in order
            if hashes.get(
                algorithm
            )
        ]

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return analyzer information.
        """

        return {
            "name": self.name,
            "description": (
                self.description
            ),
            "version": self.version,
            "cryptographic_hashes": list(
                self.CRYPTOGRAPHIC_HASHES
            ),
            "perceptual_hashes": list(
                self.PERCEPTUAL_HASHES
            ),
            "weights": dict(
                self.DEFAULT_WEIGHTS
            ),
        }