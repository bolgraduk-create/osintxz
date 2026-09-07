"""
Lexical search retriever.

Unified lexical retrieval backed by BM25.

Architecture:

InvestigationSearchQuery
        ↓
LexicalSearchRetriever
        ↓
SearchIndexRepository
        ↓
BM25SearchService
        ↓
SearchScoreNormalizer
        ↓
InvestigationSearchHit[]
        ↓
UnifiedSearchService
        ↓
RRF

Responsibilities:

- retrieve SearchIndex objects for one case
- build BM25 searchable representations
- rank candidates with BM25
- normalize raw BM25 scores into 0.0-1.0
- convert results into InvestigationSearchHit objects

Does NOT:

- perform fuzzy search
- perform semantic/vector search
- perform rank fusion
- perform graph analysis
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)

from app.services.bm25_search_service import (
    BM25Result,
    BM25SearchService,
)

from app.services.search_retriever import (
    SearchRetriever,
    SearchRetrieverInfo,
)

from app.services.search_score_normalizer import (
    SearchScoreNormalizer,
)


@dataclass(
    frozen=True,
    slots=True,
)
class LexicalSearchRetrieverConfig:
    """
    Configuration for BM25 lexical retrieval.

    title_boost controls how many times title text
    participates in the searchable representation.

    This is a lightweight field boost.

    A future BM25F implementation may replace this
    without changing the retriever contract.
    """

    title_boost: int = 2

    maximum_content_length: int = 100_000

    def __post_init__(
        self,
    ) -> None:

        if self.title_boost < 1:

            raise ValueError(
                "title_boost must be at least 1."
            )

        if self.maximum_content_length < 1:

            raise ValueError(
                "maximum_content_length must "
                "be at least 1."
            )


class LexicalSearchRetriever(
    SearchRetriever
):
    """
    Unified BM25 lexical retriever.
    """

    def __init__(
        self,
        repository: SearchIndexRepository,
        bm25_search_service: BM25SearchService
        | None = None,
        score_normalizer: SearchScoreNormalizer
        | None = None,
        config: LexicalSearchRetrieverConfig
        | None = None,
    ) -> None:

        self.repository = repository

        self.bm25_search_service = (
            bm25_search_service
            or BM25SearchService()
        )

        self.score_normalizer = (
            score_normalizer
            or SearchScoreNormalizer()
        )

        self.config = (
            config
            or LexicalSearchRetrieverConfig()
        )

        self._info = SearchRetrieverInfo(
            name="lexical",
            method=SearchMethod.LEXICAL,
            description=(
                "BM25 lexical search over "
                "investigation indexes."
            ),
            enabled=True,
            priority=100,
        )

    @property
    def info(
        self,
    ) -> SearchRetrieverInfo:

        return self._info

    def can_handle(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:

        return (
            query.has_text_query
            and query.case_id is not None
        )

    def retrieve(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        InvestigationSearchHit
    ]:

        if not self.can_handle(
            query
        ):

            return []

        indexes = (
            self.repository.get_by_case(
                query.case_id
            )
        )

        indexes = self._filter_indexes(
            indexes,
            query,
        )

        if not indexes:

            return []

        documents = [
            (
                index,
                self._build_searchable_text(
                    index
                ),
            )
            for index in indexes
        ]

        bm25_results = (
            self.bm25_search_service.rank(
                query.query,
                documents,
            )
        )

        if not bm25_results:

            return []

        raw_scores = [
            result.score
            for result in bm25_results
        ]

        normalized_scores = (
            self.score_normalizer
            .normalize(
                raw_scores
            )
        )

        hits: list[
            InvestigationSearchHit
        ] = []

        for (
            result,
            normalized_score,
        ) in zip(
            bm25_results,
            normalized_scores,
        ):

            if (
                normalized_score
                < query.minimum_score
            ):

                continue

            hit = self._build_hit(
                result=result,
                normalized_score=(
                    normalized_score
                ),
                query=query.query,
            )

            hits.append(
                hit
            )

            if (
                len(
                    hits
                )
                >= query.candidate_limit
            ):

                break

        return hits

    def _filter_indexes(
        self,
        indexes,
        query: InvestigationSearchQuery,
    ):
        """
        Apply unified scope filters.
        """

        allowed_types = {
            value
            .strip()
            .lower()

            for value
            in query.object_types

            if value
            and value.strip()
        }

        allowed_ids = set(
            query.object_ids
        )

        filtered = []

        for index in indexes:

            if (
                not query.include_deleted
                and getattr(
                    index,
                    "deleted_at",
                    None,
                )
                is not None
            ):

                continue

            object_type = (
                index.object_type.value
                if hasattr(
                    index.object_type,
                    "value",
                )
                else str(
                    index.object_type
                )
            )

            object_type = (
                object_type
                .strip()
                .lower()
            )

            if (
                allowed_types
                and object_type
                not in allowed_types
            ):

                continue

            if (
                allowed_ids
                and index.object_id
                not in allowed_ids
            ):

                continue

            filtered.append(
                index
            )

        return filtered

    def _build_searchable_text(
        self,
        index,
    ) -> str:
        """
        Build BM25 document representation.

        Title receives a small field boost by repetition.

        Example:

            title_boost = 2

            title
            title
            content
        """

        title = (
            index.title
            or ""
        )

        content = (
            index.content
            or ""
        )

        content = content[
            :self.config.maximum_content_length
        ]

        parts: list[str] = []

        if title:

            parts.extend(
                [
                    title
                    for _ in range(
                        self.config.title_boost
                    )
                ]
            )

        if content:

            parts.append(
                content
            )

        return "\n".join(
            parts
        )

    def _build_hit(
        self,
        *,
        result: BM25Result,
        normalized_score: float,
        query: str,
    ) -> InvestigationSearchHit:

        index = result.payload

        object_type = (
            index.object_type.value
            if hasattr(
                index.object_type,
                "value",
            )
            else str(
                index.object_type
            )
        )

        hit = InvestigationSearchHit(
            object_id=index.object_id,
            object_type=object_type,
            case_id=index.case_id,
            title=(
                index.title
                or ""
            ),
            snippet=(
                self._build_snippet(
                    index.content
                    or "",
                    result.matched_terms,
                )
            ),
            scores=SearchScores(
                lexical=normalized_score,
            ),
            matched_methods=[
                SearchMethod.LEXICAL,
            ],
            source=index,
            metadata={
                "search_index_id": str(
                    index.id
                ),
                "bm25_raw_score": (
                    result.score
                ),
                "bm25_rank": (
                    result.rank
                ),
                "bm25_matched_terms": (
                    list(
                        result.matched_terms
                    )
                ),
            },
        )

        hit.add_reason(
            SearchMatchReason(
                reason=(
                    self._build_reason(
                        result
                    )
                ),
                method=(
                    SearchMethod.LEXICAL
                ),
                score=(
                    normalized_score
                ),
                details={
                    "raw_bm25_score": (
                        result.score
                    ),
                    "rank": (
                        result.rank
                    ),
                    "matched_terms": (
                        list(
                            result.matched_terms
                        )
                    ),
                    "query": query,
                },
            )
        )

        return hit

    @staticmethod
    def _build_reason(
        result: BM25Result,
    ) -> str:

        term_count = len(
            result.matched_terms
        )

        if term_count == 1:

            return (
                "BM25 lexical match on "
                "1 query term."
            )

        return (
            "BM25 lexical match on "
            f"{term_count} query terms."
        )

    @staticmethod
    def _build_snippet(
        content: str,
        matched_terms: tuple[
            str,
            ...
        ],
        *,
        context_size: int = 120,
    ) -> str:

        if not content:

            return ""

        if not matched_terms:

            return (
                content[
                    :context_size * 2
                ]
                .strip()
            )

        normalized_content = (
            content.casefold()
        )

        positions = [
            normalized_content.find(
                term.casefold()
            )
            for term in matched_terms
        ]

        positions = [
            position
            for position in positions
            if position >= 0
        ]

        if not positions:

            return (
                content[
                    :context_size * 2
                ]
                .strip()
            )

        position = min(
            positions
        )

        start = max(
            0,
            position
            - context_size,
        )

        end = min(
            len(
                content
            ),
            position
            + context_size
            + max(
                len(
                    term
                )
                for term
                in matched_terms
            ),
        )

        snippet = (
            content[
                start:end
            ]
            .strip()
        )

        if start > 0:

            snippet = (
                "..."
                + snippet
            )

        if end < len(
            content
        ):

            snippet = (
                snippet
                + "..."
            )

        return snippet