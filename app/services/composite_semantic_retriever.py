"""
Composite semantic retriever.

Combines two semantic retrieval strategies behind one
SearchRetriever contract:

1. Message semantic search
   -> conversation semantic chunks
   -> Message expansion
   -> local Message reranking

2. Non-Message semantic search
   -> SearchIndex embeddings
   -> pgvector cosine retrieval

Architecture:

InvestigationSearchQuery
        ↓
CompositeSemanticRetriever
        ↓
ONE query embedding
        ↓
        ├── SemanticChunkRetriever
        │       ↓
        │    Message hits
        │
        └── SemanticSearchRetriever
                ↓
             non-Message hits
        ↓
semantic candidate merge
        ↓
UnifiedSearchService
        ↓
RRF

Responsibilities:

- generate one shared query embedding
- route Message semantic search to chunks
- route non-Message semantic search to SearchIndex vectors
- merge both semantic result streams
- preserve real semantic scores
- preserve internal Message reranking

Does NOT:

- generate stored embeddings
- perform lexical search
- perform fuzzy retrieval
- perform final cross-method RRF
- interact with UI
"""

from __future__ import annotations

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
)

from app.models.search_index import (
    SearchObjectType,
)

from app.services.embedding_service import (
    EmbeddingService,
)

from app.services.search_retriever import (
    SearchRetriever,
    SearchRetrieverInfo,
)

from app.services.semantic_chunk_retriever import (
    SemanticChunkRetriever,
)

from app.services.semantic_search_retriever import (
    SemanticSearchRetriever,
)


class CompositeSemanticRetriever(
    SearchRetriever
):
    """
    Unified semantic retriever.

    A single query embedding is shared between:

    - conversation-chunk Message search
    - regular SearchIndex vector search
    """

    MESSAGE_OBJECT_TYPE = "message"

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        message_retriever: SemanticChunkRetriever,
        object_retriever: SemanticSearchRetriever,
    ) -> None:

        self.embedding_service = (
            embedding_service
        )

        self.message_retriever = (
            message_retriever
        )

        self.object_retriever = (
            object_retriever
        )

        self._info = SearchRetrieverInfo(
            name="semantic",
            method=SearchMethod.SEMANTIC,
            description=(
                "Composite semantic search using "
                "conversation chunks for Messages and "
                "SearchIndex vectors for other objects."
            ),
            enabled=True,
            priority=300,
        )

    # ======================================================
    # Retriever information
    # ======================================================

    @property
    def info(
        self,
    ) -> SearchRetrieverInfo:

        return self._info

    # ======================================================
    # Compatibility
    # ======================================================

    def can_handle(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Composite semantic search requires textual input
        and investigation case scope.
        """

        return (
            query.has_text_query
            and query.case_id is not None
        )

    # ======================================================
    # Retrieval
    # ======================================================

    def retrieve(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Execute all appropriate semantic strategies while
        generating the query embedding exactly once.
        """

        if not self.can_handle(
            query
        ):

            return []

        # --------------------------------------------------
        # ONE shared query embedding
        # --------------------------------------------------

        query_embedding = (
            self.embedding_service.embed(
                query.query
            )
        )

        message_hits: list[
            InvestigationSearchHit
        ] = []

        object_hits: list[
            InvestigationSearchHit
        ] = []

        # --------------------------------------------------
        # Message semantic branch
        # --------------------------------------------------

        if self._wants_messages(
            query
        ):

            message_hits = (
                self.message_retriever
                .retrieve_with_embedding(
                    query=query,
                    query_embedding=(
                        query_embedding
                    ),
                )
            )

        # --------------------------------------------------
        # Non-Message semantic branch
        # --------------------------------------------------

        object_types = (
            self._non_message_object_types(
                query
            )
        )

        if object_types:

            object_hits = (
                self.object_retriever
                .retrieve_with_embedding(
                    query=query,
                    query_embedding=(
                        query_embedding
                    ),
                    object_types=(
                        object_types
                    ),
                )
            )

        # --------------------------------------------------
        # Merge
        # --------------------------------------------------

        return self._merge_hits(
            message_hits=message_hits,
            object_hits=object_hits,
            candidate_limit=(
                query.candidate_limit
            ),
        )

    # ======================================================
    # Routing
    # ======================================================

    def _wants_messages(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Determine whether Message semantic retrieval should
        participate.

        Empty object_types means all object types.
        """

        if not query.object_types:

            return True

        normalized = {
            self._normalize_object_type(
                value
            )
            for value
            in query.object_types
        }

        return (
            self.MESSAGE_OBJECT_TYPE
            in normalized
        )

    def _non_message_object_types(
        self,
        query: InvestigationSearchQuery,
    ) -> tuple[str, ...]:
        """
        Determine object types handled by the regular
        SearchIndex semantic retriever.

        Messages are always excluded because Message
        semantics are owned by SemanticChunkRetriever.
        """

        if query.object_types:

            normalized = [
                self._normalize_object_type(
                    value
                )
                for value
                in query.object_types
            ]

            return tuple(
                value
                for value
                in normalized
                if (
                    value
                    and value
                    != self.MESSAGE_OBJECT_TYPE
                )
            )

        # --------------------------------------------------
        # No explicit type filter:
        #
        # dynamically use every SearchObjectType except
        # Message.
        #
        # This avoids hardcoding the project's complete
        # searchable object-type list here.
        # --------------------------------------------------

        result: list[str] = []

        for object_type in SearchObjectType:

            value = (
                object_type.value
                if hasattr(
                    object_type,
                    "value",
                )
                else str(
                    object_type
                )
            )

            normalized = (
                self._normalize_object_type(
                    value
                )
            )

            if (
                normalized
                and normalized
                != self.MESSAGE_OBJECT_TYPE
            ):

                result.append(
                    normalized
                )

        return tuple(
            result
        )

    # ======================================================
    # Merge
    # ======================================================

    def _merge_hits(
        self,
        *,
        message_hits: list[
            InvestigationSearchHit
        ],
        object_hits: list[
            InvestigationSearchHit
        ],
        candidate_limit: int,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Merge semantic branches into one ranked stream.

        Important:

        SearchScores.semantic remains the true cosine
        semantic similarity.

        For Message hits only, the internal
        semantic_message_ranking_score is used for ordering
        because it contains the lightweight local Message
        reranking signal.

        That internal ranking value is NOT written into the
        semantic score.
        """

        best_by_object: dict[
            tuple[str, object],
            InvestigationSearchHit,
        ] = {}

        for hit in (
            message_hits
            + object_hits
        ):

            key = (
                self._normalize_object_type(
                    hit.object_type
                ),
                hit.object_id,
            )

            existing = (
                best_by_object.get(
                    key
                )
            )

            if existing is None:

                best_by_object[
                    key
                ] = hit

                continue

            if (
                self._ranking_value(
                    hit
                )
                >
                self._ranking_value(
                    existing
                )
            ):

                best_by_object[
                    key
                ] = hit

        merged = list(
            best_by_object.values()
        )

        merged.sort(
            key=lambda hit: (
                self._ranking_value(
                    hit
                ),
                self._semantic_value(
                    hit
                ),
            ),
            reverse=True,
        )

        return merged[
            :candidate_limit
        ]

    # ======================================================
    # Ranking helpers
    # ======================================================

    def _ranking_value(
        self,
        hit: InvestigationSearchHit,
    ) -> float:
        """
        Internal composite ordering value.

        Message:
            local semantic Message reranking score.

        Other objects:
            cosine semantic similarity.
        """

        if (
            self._normalize_object_type(
                hit.object_type
            )
            == self.MESSAGE_OBJECT_TYPE
        ):

            value = (
                hit.metadata.get(
                    "semantic_message_ranking_score"
                )
            )

            if value is not None:

                try:

                    return float(
                        value
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    pass

        return (
            self._semantic_value(
                hit
            )
        )

    @staticmethod
    def _semantic_value(
        hit: InvestigationSearchHit,
    ) -> float:
        """
        Return real semantic score for secondary ordering.
        """

        value = (
            hit.scores.semantic
        )

        if value is None:

            return 0.0

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

    # ======================================================
    # Normalization
    # ======================================================

    @staticmethod
    def _normalize_object_type(
        value,
    ) -> str:
        """
        Normalize enum/string object type.
        """

        if hasattr(
            value,
            "value",
        ):

            value = (
                value.value
            )

        return (
            str(
                value
                or ""
            )
            .strip()
            .lower()
        )