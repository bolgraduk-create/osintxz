"""
Fuzzy name resolution signals.

Adapts the existing FuzzySearchService for
entity identity resolution.

Responsibilities:

- compare PERSON and ORGANIZATION names
- reuse existing Levenshtein / Jaro-Winkler /
  trigram mathematics
- support token-order-insensitive comparison
- create explainable name similarity signals
- preserve individual fuzzy component scores

Does NOT:

- implement fuzzy algorithms
- treat dissimilar names as contradictions
- calculate final identity score
- decide MATCH / REVIEW / NO_MATCH
- merge entities
- access the database
"""

from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from app.entity_resolution.contracts import (
    EntityResolutionReason,
    EntityResolutionSignal,
    EntityResolutionSignalDirection,
    EntityResolutionSignalType,
)

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.models.entity import (
    Entity,
    EntityType,
)

from app.services.fuzzy_search_service import (
    FuzzySearchService,
    FuzzySimilarityResult,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    slots=True,
)
class FuzzyNameSignalConfig:
    """
    Configuration for fuzzy name signals.

    minimum_similarity:
        Values below this threshold do not create
        any identity-resolution signal.

    strong_similarity:
        Used only for explainability classification.
        It does NOT automatically mean MATCH.

    entity_type_weights:
        Relative importance of fuzzy name similarity
        for future multi-signal identity scoring.
    """

    minimum_similarity: float = 0.60

    strong_similarity: float = 0.85

    entity_type_weights: dict[
        EntityType,
        float,
    ] = field(
        default_factory=lambda: {
            EntityType.PERSON: 0.55,
            EntityType.ORGANIZATION: 0.45,
        }
    )

    enable_token_order_comparison: bool = True

    maximum_name_tokens: int = 8

    require_same_case: bool = True

    def __post_init__(
        self,
    ) -> None:

        self.minimum_similarity = float(
            self.minimum_similarity
        )

        self.strong_similarity = float(
            self.strong_similarity
        )

        if not (
            0.0
            <= self.minimum_similarity
            <= 1.0
        ):

            raise ValueError(
                "minimum_similarity must be "
                "between 0.0 and 1.0."
            )

        if not (
            0.0
            <= self.strong_similarity
            <= 1.0
        ):

            raise ValueError(
                "strong_similarity must be "
                "between 0.0 and 1.0."
            )

        if (
            self.strong_similarity
            <
            self.minimum_similarity
        ):

            raise ValueError(
                "strong_similarity cannot be "
                "below minimum_similarity."
            )

        if self.maximum_name_tokens < 1:

            raise ValueError(
                "maximum_name_tokens must "
                "be positive."
            )

        for (
            entity_type,
            weight,
        ) in self.entity_type_weights.items():

            normalized_weight = float(
                weight
            )

            if normalized_weight < 0.0:

                raise ValueError(
                    "Entity type fuzzy-name "
                    "weight cannot be negative."
                )

            self.entity_type_weights[
                entity_type
            ] = normalized_weight


# ==========================================================
# Builder
# ==========================================================


class FuzzyNameSignalBuilder:
    """
    Build fuzzy name identity signals.

    Existing FuzzySearchService remains the only
    implementation of fuzzy string mathematics.
    """

    def __init__(
        self,
        *,
        normalizer: EntityNormalizer | None = None,
        fuzzy_search_service: (
            FuzzySearchService
            | None
        ) = None,
        config: (
            FuzzyNameSignalConfig
            | None
        ) = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

        self.fuzzy_search_service = (
            fuzzy_search_service
            or FuzzySearchService()
        )

        self.config = (
            config
            or FuzzyNameSignalConfig()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        first: Entity,
        second: Entity,
    ) -> list[
        EntityResolutionSignal
    ]:
        """
        Build fuzzy name support signals.

        Returns either:

        - one SUPPORT signal
        - an empty list

        Low name similarity is deliberately treated
        as absence of support, not contradiction.
        """

        first_type = (
            self._resolve_entity_type(
                getattr(
                    first,
                    "entity_type",
                    None,
                )
            )
        )

        second_type = (
            self._resolve_entity_type(
                getattr(
                    second,
                    "entity_type",
                    None,
                )
            )
        )

        if (
            first_type is None
            or second_type is None
            or first_type != second_type
        ):

            return []

        weight = (
            self.config
            .entity_type_weights
            .get(
                first_type
            )
        )

        if weight is None:

            return []

        if (
            self.config.require_same_case
            and (
                getattr(
                    first,
                    "case_id",
                    None,
                )
                !=
                getattr(
                    second,
                    "case_id",
                    None,
                )
            )
        ):

            return []

        first_name = (
            self._canonical_name(
                first,
                first_type,
            )
        )

        second_name = (
            self._canonical_name(
                second,
                second_type,
            )
        )

        if (
            not first_name
            or not second_name
        ):

            return []

        direct_result = (
            self.fuzzy_search_service
            .compare(
                first_name,
                second_name,
            )
        )

        token_result = None

        if self._should_compare_token_order(
            first_name,
            second_name,
        ):

            token_result = (
                self._compare_sorted_tokens(
                    first_name,
                    second_name,
                )
            )

        (
            selected_result,
            comparison_mode,
        ) = self._select_result(
            direct_result=direct_result,
            token_result=token_result,
        )

        similarity = float(
            selected_result.combined
        )

        if (
            similarity
            <
            self.config.minimum_similarity
        ):

            return []

        similarity_band = (
            "strong"
            if (
                similarity
                >=
                self.config
                .strong_similarity
            )
            else
            "moderate"
        )

        signal = EntityResolutionSignal(
            name=(
                f"{first_type.value}"
                "_name_similarity"
            ),
            signal_type=(
                EntityResolutionSignalType
                .NAME_SIMILARITY
            ),
            direction=(
                EntityResolutionSignalDirection
                .SUPPORT
            ),
            score=similarity,
            weight=weight,
            reason=(
                self._build_reason(
                    entity_type=first_type,
                    similarity_band=(
                        similarity_band
                    ),
                    comparison_mode=(
                        comparison_mode
                    ),
                )
            ),
            details={
                "entity_type": (
                    first_type.value
                ),
                "comparison_mode": (
                    comparison_mode
                ),
                "similarity_band": (
                    similarity_band
                ),
                "minimum_similarity": (
                    self.config
                    .minimum_similarity
                ),
                "strong_similarity": (
                    self.config
                    .strong_similarity
                ),
                "canonical_first": (
                    first_name
                ),
                "canonical_second": (
                    second_name
                ),
                "combined": (
                    selected_result.combined
                ),
                "levenshtein": (
                    selected_result
                    .levenshtein
                ),
                "jaro_winkler": (
                    selected_result
                    .jaro_winkler
                ),
                "trigram": (
                    selected_result.trigram
                ),
                "normalized_first": (
                    selected_result
                    .normalized_left
                ),
                "normalized_second": (
                    selected_result
                    .normalized_right
                ),
                "direct": (
                    self._result_details(
                        direct_result
                    )
                ),
                "token_order": (
                    self._result_details(
                        token_result
                    )
                    if token_result
                    is not None
                    else None
                ),
            },
        )

        return [
            signal
        ]

    def build_reasons(
        self,
        signals: list[
            EntityResolutionSignal
        ],
    ) -> list[
        EntityResolutionReason
    ]:
        """
        Convert fuzzy-name signals into
        explainability reasons.
        """

        reasons: list[
            EntityResolutionReason
        ] = []

        for signal in signals:

            if (
                signal.signal_type
                !=
                EntityResolutionSignalType
                .NAME_SIMILARITY
            ):

                continue

            reasons.append(
                EntityResolutionReason(
                    code=signal.name,
                    message=signal.reason,
                    direction=signal.direction,
                    signal_name=signal.name,
                    score=signal.score,
                    details=dict(
                        signal.details
                    ),
                )
            )

        return reasons

    # ==========================================================
    # Name preparation
    # ==========================================================

    def _canonical_name(
        self,
        entity: Entity,
        entity_type: EntityType,
    ) -> str:

        normalized_value = getattr(
            entity,
            "normalized_value",
            None,
        )

        raw_value = getattr(
            entity,
            "value",
            "",
        )

        source_value = (
            normalized_value
            if normalized_value
            not in (
                None,
                "",
            )
            else raw_value
        )

        return self.normalizer.normalize(
            entity_type,
            source_value,
        )

    # ==========================================================
    # Token-order comparison
    # ==========================================================

    def _should_compare_token_order(
        self,
        first: str,
        second: str,
    ) -> bool:

        if (
            not self.config
            .enable_token_order_comparison
        ):

            return False

        first_tokens = (
            first.split()
        )

        second_tokens = (
            second.split()
        )

        if (
            len(first_tokens) < 2
            or len(second_tokens) < 2
        ):

            return False

        if (
            len(first_tokens)
            >
            self.config.maximum_name_tokens
            or
            len(second_tokens)
            >
            self.config.maximum_name_tokens
        ):

            return False

        return True

    def _compare_sorted_tokens(
        self,
        first: str,
        second: str,
    ) -> FuzzySimilarityResult:

        first_sorted = " ".join(
            sorted(
                first.split()
            )
        )

        second_sorted = " ".join(
            sorted(
                second.split()
            )
        )

        return (
            self.fuzzy_search_service
            .compare(
                first_sorted,
                second_sorted,
            )
        )

    # ==========================================================
    # Result selection
    # ==========================================================

    @staticmethod
    def _select_result(
        *,
        direct_result: (
            FuzzySimilarityResult
        ),
        token_result: (
            FuzzySimilarityResult
            | None
        ),
    ) -> tuple[
        FuzzySimilarityResult,
        str,
    ]:
        """
        Select strongest comparison.

        Direct comparison wins ties to keep
        the original name order preferred.
        """

        if token_result is None:

            return (
                direct_result,
                "direct",
            )

        if (
            token_result.combined
            >
            direct_result.combined
        ):

            return (
                token_result,
                "token_sorted",
            )

        return (
            direct_result,
            "direct",
        )

    # ==========================================================
    # Explainability
    # ==========================================================

    @staticmethod
    def _build_reason(
        *,
        entity_type: EntityType,
        similarity_band: str,
        comparison_mode: str,
    ) -> str:

        readable_type = (
            "Person"
            if (
                entity_type
                ==
                EntityType.PERSON
            )
            else
            "Organization"
        )

        if (
            comparison_mode
            ==
            "token_sorted"
        ):

            return (
                f"{readable_type} names have "
                f"{similarity_band} fuzzy similarity "
                "after token-order normalization."
            )

        return (
            f"{readable_type} names have "
            f"{similarity_band} fuzzy similarity."
        )

    @staticmethod
    def _result_details(
        result: FuzzySimilarityResult,
    ) -> dict[str, Any]:

        return {
            "combined": result.combined,
            "levenshtein": (
                result.levenshtein
            ),
            "jaro_winkler": (
                result.jaro_winkler
            ),
            "trigram": result.trigram,
            "normalized_left": (
                result.normalized_left
            ),
            "normalized_right": (
                result.normalized_right
            ),
            "exact": result.exact,
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _resolve_entity_type(
        value: Any,
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