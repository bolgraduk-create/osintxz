"""
Unified search retriever contract.

Defines the common interface implemented by every
retrieval mechanism participating in Unified Search.

Architecture:

InvestigationSearchQuery
        ↓
UnifiedSearchService
        ↓
SearchRetriever
    ├── StructuredRetriever
    ├── LexicalRetriever
    ├── FuzzyRetriever
    ├── SemanticRetriever
    └── ImageRetriever
        ↓
InvestigationSearchHit

Responsibilities:

- define one common retriever interface
- describe retriever capabilities
- validate whether a retriever can handle a query
- return unified InvestigationSearchHit objects

Does NOT:

- perform rank fusion
- perform final ranking
- perform analytical enrichment
- manage UI
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
)


# ==========================================================
# Retriever information
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchRetrieverInfo:
    """
    Static information about one retrieval mechanism.
    """

    name: str

    method: SearchMethod

    description: str = ""

    enabled: bool = True

    priority: int = 100

    def __post_init__(
        self,
    ) -> None:
        """
        Validate retriever metadata.
        """

        normalized_name = (
            self.name
            .strip()
        )

        if not normalized_name:

            raise ValueError(
                "Retriever name cannot be empty."
            )

        object.__setattr__(
            self,
            "name",
            normalized_name,
        )

        object.__setattr__(
            self,
            "description",
            self.description.strip(),
        )

        if (
            self.method
            == SearchMethod.AUTO
        ):

            raise ValueError(
                "A retriever cannot use "
                "SearchMethod.AUTO."
            )


# ==========================================================
# Base retriever
# ==========================================================


class SearchRetriever(
    ABC
):
    """
    Base contract for all search retrievers.

    Every search mechanism must implement this
    interface before it can participate in the
    Unified Investigation Search pipeline.
    """

    # ======================================================
    # Retriever metadata
    # ======================================================

    @property
    @abstractmethod
    def info(
        self,
    ) -> SearchRetrieverInfo:
        """
        Return retriever metadata.
        """

        raise NotImplementedError

    # ======================================================
    # Query compatibility
    # ======================================================

    def supports(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Check whether this retriever should participate
        in the current search request.

        Subclasses may extend this method with additional
        compatibility checks.
        """

        if not self.info.enabled:

            return False

        if not query.uses_method(
            self.info.method
        ):

            return False

        return self.can_handle(
            query
        )

    def can_handle(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Check whether the query contains input this
        retriever can process.

        Default behaviour is suitable for text-based
        retrievers.

        Image and other source-object retrievers should
        override this method.
        """

        return query.has_text_query

    # ======================================================
    # Retrieval
    # ======================================================

    @abstractmethod
    def retrieve(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Execute retrieval and return unified candidates.

        Returned results must:

        - use normalized 0.0-1.0 scores
        - contain stable object identity
        - identify the matching SearchMethod
        - not perform final cross-retriever ranking
        """

        raise NotImplementedError

    # ======================================================
    # Helpers
    # ======================================================

    @property
    def name(
        self,
    ) -> str:
        """
        Convenience access to retriever name.
        """

        return self.info.name

    @property
    def method(
        self,
    ) -> SearchMethod:
        """
        Convenience access to retriever method.
        """

        return self.info.method

    @property
    def priority(
        self,
    ) -> int:
        """
        Retriever execution priority.

        Lower values run first.
        """

        return self.info.priority

    @property
    def enabled(
        self,
    ) -> bool:
        """
        Whether retriever is enabled.
        """

        return self.info.enabled