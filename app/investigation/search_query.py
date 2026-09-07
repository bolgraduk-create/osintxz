"""
Unified investigation search query.

Defines the common input contract used by all
investigation search mechanisms.

Architecture:

Desktop / API / AI
        ↓
InvestigationSearchQuery
        ↓
UnifiedSearchService
        ↓
Retrievers
    ├── structured
    ├── lexical
    ├── fuzzy
    ├── semantic
    ├── image
    └── future retrievers

Responsibilities:

- represent one investigation search request
- keep search scope in one place
- define result limits and thresholds
- define which retrieval methods may participate
- control optional post-fusion reranking layers
- carry optional search metadata

Does NOT:

- execute search
- access repositories
- calculate similarity
- rank results
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from uuid import UUID




@dataclass(slots=True)
class StructuredSearchFilters:
    """
    Typed filters used by StructuredSearchRetriever.

    The Investigation contract intentionally keeps model-specific enum
    classes out of this module. Retrievers validate the string values
    against their persistence models at the infrastructure boundary.
    """

    entity_types: tuple[str, ...] = field(default_factory=tuple)
    evidence_types: tuple[str, ...] = field(default_factory=tuple)
    source_ids: tuple[UUID, ...] = field(default_factory=tuple)
    values: tuple[str, ...] = field(default_factory=tuple)
    normalized_values: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.entity_types = self._normalize_strings(self.entity_types)
        self.evidence_types = self._normalize_strings(self.evidence_types)
        self.values = self._normalize_strings(self.values, casefold=False)
        self.normalized_values = self._normalize_strings(
            self.normalized_values,
            casefold=False,
        )

    @property
    def is_empty(self) -> bool:
        return not (
            self.entity_types
            or self.evidence_types
            or self.source_ids
            or self.values
            or self.normalized_values
        )

    @staticmethod
    def _normalize_strings(
        values: tuple[str, ...],
        *,
        casefold: bool = True,
    ) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()

        for value in values:
            raw_value = getattr(value, "value", value)
            item = str(raw_value or "").strip()
            if not item:
                continue
            if casefold:
                item = item.casefold()
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)

        return tuple(normalized)


class SearchMethod(str, Enum):
    """
    Search mechanisms available to the unified
    investigation search engine.

    AUTO means that UnifiedSearchService decides
    which registered mechanisms should participate.
    """

    AUTO = "auto"

    STRUCTURED = "structured"

    LEXICAL = "lexical"

    FUZZY = "fuzzy"

    SEMANTIC = "semantic"

    IMAGE = "image"


@dataclass(slots=True)
class InvestigationSearchQuery:
    """
    One unified investigation search request.

    The same object is passed through the entire
    search pipeline.

    Individual retrievers may use only the fields
    relevant to them.
    """

    # ==========================================================
    # Main query
    # ==========================================================

    query: str = ""

    # ==========================================================
    # Investigation scope
    # ==========================================================

    case_id: UUID | None = None

    object_types: tuple[str, ...] = field(
        default_factory=tuple
    )

    object_ids: tuple[UUID, ...] = field(
        default_factory=tuple
    )

    # ==========================================================
    # Search methods
    # ==========================================================

    methods: tuple[SearchMethod, ...] = (
        SearchMethod.AUTO,
    )

    # ==========================================================
    # Result control
    # ==========================================================

    limit: int = 50

    candidate_limit: int = 200

    minimum_score: float = 0.0

    # ==========================================================
    # Search behaviour
    # ==========================================================

    include_deleted: bool = False

    enable_query_expansion: bool = True

    enable_reranking: bool = True

    # ==========================================================
    # Optional contextual input
    # ==========================================================

    source_object_id: UUID | None = None

    source_object_type: str | None = None

    # ==========================================================
    # Runtime metadata
    # ==========================================================

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ==========================================================
    # Optional post-fusion refinement control
    # ==========================================================

    # Kept at the end of the dataclass field list so existing
    # positional construction of older fields remains compatible.
    enable_neural_reranking: bool = True

    # ==========================================================
    # Typed structured retrieval
    # ==========================================================

    structured_filters: StructuredSearchFilters = field(
        default_factory=StructuredSearchFilters
    )

    # ==========================================================
    # Validation
    # ==========================================================

    def __post_init__(
        self,
    ) -> None:
        """
        Normalize and validate query parameters.
        """

        self.query = self.query.strip()

        if self.limit < 1:
            raise ValueError(
                "Search result limit must be at least 1."
            )

        if self.candidate_limit < 1:
            raise ValueError(
                "Search candidate limit must be at least 1."
            )

        if self.candidate_limit < self.limit:
            self.candidate_limit = self.limit

        if not 0.0 <= self.minimum_score <= 1.0:
            raise ValueError(
                "minimum_score must be between 0.0 and 1.0."
            )

        self.methods = self._normalize_methods(
            self.methods
        )

        self.object_types = tuple(
            value.strip().lower()
            for value in self.object_types
            if value
            and value.strip()
        )

        if not isinstance(
            self.structured_filters,
            StructuredSearchFilters,
        ):
            raise TypeError(
                "structured_filters must be StructuredSearchFilters."
            )

    # ==========================================================
    # Search method helpers
    # ==========================================================

    def uses_method(
        self,
        method: SearchMethod,
    ) -> bool:
        """
        Check whether a search mechanism is enabled.

        AUTO allows UnifiedSearchService to use
        every appropriate registered retriever.
        """

        return (
            SearchMethod.AUTO
            in self.methods
            or method
            in self.methods
        )

    @property
    def automatic(
        self,
    ) -> bool:
        """
        Whether search mechanism selection is automatic.
        """

        return (
            SearchMethod.AUTO
            in self.methods
        )

    # ==========================================================
    # Query helpers
    # ==========================================================

    @property
    def has_text_query(
        self,
    ) -> bool:
        """
        Whether the request contains textual input.
        """

        return bool(
            self.query
        )

    @property
    def has_source_object(
        self,
    ) -> bool:
        """
        Whether search is based on an existing
        investigation object.

        Example:

        Find Similar for an image.
        """

        return (
            self.source_object_id
            is not None
        )

    @property
    def has_structured_input(self) -> bool:
        """Whether the request contains explicit structured scope/filter input."""

        structured_object_types = {"entity", "evidence"}

        return bool(
            self.object_ids
            or not self.structured_filters.is_empty
            or (
                not self.has_text_query
                and bool(
                    structured_object_types.intersection(
                        self.object_types
                    )
                )
            )
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        """
        Whether request contains no usable search input.
        """

        return (
            not self.has_text_query
            and not self.has_source_object
            and not self.object_ids
            and not self.has_structured_input
        )

    # ==========================================================
    # Internal helpers
    # ==========================================================

    @staticmethod
    def _normalize_methods(
        methods: tuple[
            SearchMethod,
            ...
        ],
    ) -> tuple[
        SearchMethod,
        ...
    ]:
        """
        Normalize search method collection.
        """

        if not methods:
            return (
                SearchMethod.AUTO,
            )

        normalized: list[
            SearchMethod
        ] = []

        for method in methods:

            if not isinstance(
                method,
                SearchMethod,
            ):

                method = SearchMethod(
                    method
                )

            if method not in normalized:
                normalized.append(
                    method
                )

        if (
            SearchMethod.AUTO
            in normalized
        ):
            return (
                SearchMethod.AUTO,
            )

        return tuple(
            normalized
        )
