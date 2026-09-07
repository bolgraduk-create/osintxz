"""
Semantic chunk search retriever.

Connects conversation-level semantic chunk retrieval
with UnifiedSearchService while returning real Message
objects as search hits.

Architecture:

InvestigationSearchQuery
        ↓
SemanticChunkRetriever
        ↓
EmbeddingService
        ↓
query embedding
        ↓
SearchSemanticChunkEmbeddingRepository
        ↓
pgvector cosine search
        ↓
top SearchSemanticChunk[]
        ↓
message_ids[]
        ↓
MessageRepository.get_by_ids()
        ↓
InvestigationSearchHit[Message]
        ↓
UnifiedSearchService
        ↓
RRF

Important:

Semantic chunks are an internal optimization layer.

They are never exposed as final investigation search
objects. The user receives the original Message records.

Responsibilities:

- generate one query embedding
- retrieve semantically relevant conversation chunks
- expand chunks into their original messages
- perform message-level candidate filtering
- deduplicate messages
- convert messages into unified search hits
- preserve chunk provenance in metadata

Does NOT:

- build semantic chunks
- generate stored chunk embeddings
- perform lexical retrieval
- perform fuzzy retrieval
- perform rank fusion
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.investigation.search_query import (
    InvestigationSearchQuery,
    SearchMethod,
)

from app.investigation.search_result import (
    InvestigationSearchHit,
    SearchMatchReason,
    SearchScores,
)

from app.models.message import (
    Message,
)

from app.repositories.message_repository import (
    MessageRepository,
)

from app.repositories.search_semantic_chunk_embedding_repository import (
    SearchSemanticChunkEmbeddingRepository,
    SemanticChunkSimilarityResult,
)

from app.services.embedding_service import (
    EmbeddingService,
)

from app.services.search_retriever import (
    SearchRetriever,
    SearchRetrieverInfo,
)

from app.services.semantic_message_reranker import (
    SemanticMessageReranker,
)

from app.services.semantic_search_retriever import (
    SemanticQueryEmbedding,
)


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SemanticChunkRetrieverConfig:
    """
    Semantic chunk retrieval configuration.

    minimum_similarity:
        Minimum cosine similarity required for a chunk.

    maximum_chunks:
        Safety limit for number of semantic chunks
        expanded into messages.

    context_position_weight:
        Optional lightweight weighting applied according
        to a message's location inside a chunk.

        A value of 0.0 means every message receives the
        chunk similarity unchanged.

        We currently keep this disabled because message
        ordering alone does not prove relevance.
    """

    minimum_similarity: float = 0.30

    maximum_chunks: int = 120

    context_position_weight: float = 0.0

    def __post_init__(
        self,
    ) -> None:

        if not (
            0.0
            <= self.minimum_similarity
            <= 1.0
        ):

            raise ValueError(
                "minimum_similarity must be "
                "between 0.0 and 1.0."
            )

        if self.maximum_chunks < 1:

            raise ValueError(
                "maximum_chunks must be at least 1."
            )

        if not (
            0.0
            <= self.context_position_weight
            <= 1.0
        ):

            raise ValueError(
                "context_position_weight must be "
                "between 0.0 and 1.0."
            )




# ==========================================================
# Internal candidate
# ==========================================================


@dataclass(
    slots=True,
)
class _SemanticMessageCandidate:
    """
    Internal semantic message candidate.

    If the same Message is reached from multiple chunks,
    the strongest semantic signal is preserved.
    """

    message: Message

    similarity: float

    distance: float

    chunk_id: UUID

    chunk_order: int

    chunk_message_count: int

    chunk_chat_name: str | None

    embedding_id: UUID

    embedding_model: str

    embedding_dimensions: int

    ranking_score: float


# ==========================================================
# Retriever
# ==========================================================


class SemanticChunkRetriever(
    SearchRetriever
):
    """
    Semantic retriever backed by conversation chunks.

    Final hits always represent original Message objects.
    """

    def __init__(
        self,
        *,
        message_reranker: SemanticMessageReranker | None = None,
        repository: (
            SearchSemanticChunkEmbeddingRepository
        ),
        message_repository: MessageRepository,
        embedding_service: EmbeddingService,
        config: (
            SemanticChunkRetrieverConfig
            | None
        ) = None,
    ) -> None:

        self.repository = (
            repository
        )

        self.message_repository = (
            message_repository
        )

        self.embedding_service = (
            embedding_service
        )

        self.config = (
            config
            or SemanticChunkRetrieverConfig()
        )

        self.message_reranker = (
            message_reranker
            or SemanticMessageReranker()
        )

        self._info = (
            SearchRetrieverInfo(
                name="semantic",
                method=SearchMethod.SEMANTIC,
                description=(
                    "Conversation-chunk semantic search "
                    "using pgvector cosine similarity."
                ),
                enabled=True,
                priority=300,
            )
        )

    # ==========================================================
    # Retriever information
    # ==========================================================

    @property
    def info(
        self,
    ) -> SearchRetrieverInfo:

        return self._info

    # ==========================================================
    # Query compatibility
    # ==========================================================

    def can_handle(
        self,
        query: InvestigationSearchQuery,
    ) -> bool:
        """
        Semantic chunk retrieval requires:

        - textual query
        - case scope
        - Message-compatible object type filter
        """

        if not (
            query.has_text_query
            and query.case_id is not None
        ):

            return False

        # ------------------------------------------------------
        # Object type filtering
        # ------------------------------------------------------
        #
        # Semantic chunks currently represent Message objects
        # only.
        #
        # If no object_types are specified, Message is allowed.
        # ------------------------------------------------------

        if query.object_types:

            normalized_types = {
                str(
                    value
                )
                .strip()
                .lower()
                for value
                in query.object_types
            }

            if "message" not in normalized_types:

                return False

        return True

    # ==========================================================
    # Retrieval
    # ==========================================================

    def retrieve(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Perform standalone Message chunk semantic retrieval.

        When used independently, one query embedding is
        generated here.

        Higher-level semantic orchestration should use
        retrieve_with_embedding() so the same query vector
        can be reused by multiple semantic strategies.
        """

        if not self.can_handle(
            query
        ):

            return []

        query_embedding = (
            self.embedding_service.embed(
                query.query
            )
        )

        return (
            self.retrieve_with_embedding(
                query=query,
                query_embedding=(
                    query_embedding
                ),
            )
        )

    def retrieve_with_embedding(
        self,
        *,
        query: InvestigationSearchQuery,
        query_embedding: SemanticQueryEmbedding,
    ) -> list[
        InvestigationSearchHit
    ]:
        """
        Perform Message semantic retrieval using an already
        generated query embedding.

        No embedding provider call occurs inside this method.

        Flow:

            shared query embedding
                    ↓
            semantic chunk retrieval
                    ↓
            matching Message IDs
                    ↓
            bulk Message loading
                    ↓
            local Message reranking
                    ↓
            InvestigationSearchHit[]
        """

        if not self.can_handle(
            query
        ):

            return []

        # ------------------------------------------------------
        # Semantic chunk recall
        # ------------------------------------------------------

        chunk_limit = min(
            self.config.maximum_chunks,
            max(
                80,
                query.candidate_limit * 4,
            ),
        )

        chunk_matches = (
            self.repository.search_similar(
                case_id=query.case_id,
                query_vector=(
                    query_embedding.vector
                ),
                model=(
                    query_embedding.model
                ),
                limit=(
                    chunk_limit
                ),
            )
        )

        # ------------------------------------------------------
        # Similarity threshold
        # ------------------------------------------------------

        minimum_similarity = max(
            self.config.minimum_similarity,
            query.minimum_score,
        )

        chunk_matches = [
            match
            for match
            in chunk_matches
            if (
                match.similarity
                >= minimum_similarity
            )
        ]

        if not chunk_matches:

            return []

        # ------------------------------------------------------
        # Map Message IDs -> matching semantic chunks
        # ------------------------------------------------------

        message_matches: dict[
            UUID,
            list[
                SemanticChunkSimilarityResult
            ],
        ] = {}

        message_ids: list[
            UUID
        ] = []

        seen_message_ids: set[
            UUID
        ] = set()

        for match in chunk_matches:

            chunk = (
                match.embedding.chunk
            )

            if chunk is None:

                continue

            for raw_message_id in (
                chunk.message_ids
                or []
            ):

                try:

                    message_id = (
                        raw_message_id
                        if isinstance(
                            raw_message_id,
                            UUID,
                        )
                        else UUID(
                            str(
                                raw_message_id
                            )
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                    AttributeError,
                ):

                    continue

                if (
                    query.object_ids
                    and message_id
                    not in query.object_ids
                ):

                    continue

                message_matches.setdefault(
                    message_id,
                    [],
                ).append(
                    match
                )

                if (
                    message_id
                    not in seen_message_ids
                ):

                    seen_message_ids.add(
                        message_id
                    )

                    message_ids.append(
                        message_id
                    )

        if not message_ids:

            return []

        # ------------------------------------------------------
        # Bulk Message retrieval
        # ------------------------------------------------------

        messages = (
            self.message_repository.get_by_ids(
                message_ids,
                case_id=query.case_id,
            )
        )

        # ------------------------------------------------------
        # Build Message candidates
        # ------------------------------------------------------

        candidates: list[
            _SemanticMessageCandidate
        ] = []

        for message in messages:

            if (
                not query.include_deleted
                and getattr(
                    message,
                    "deleted_at",
                    None,
                )
                is not None
            ):

                continue

            matching_chunks = (
                message_matches.get(
                    message.id,
                    [],
                )
            )

            if not matching_chunks:

                continue

            strongest_match = max(
                matching_chunks,
                key=lambda item: (
                    item.similarity
                ),
            )

            embedding = (
                strongest_match.embedding
            )

            chunk = (
                embedding.chunk
            )

            if chunk is None:

                continue

            similarity = (
                self._message_similarity(
                    message=message,
                    chunk=chunk,
                    similarity=(
                        strongest_match.similarity
                    ),
                )
            )

            rerank = (
                self.message_reranker.score(
                    query=query.query,
                    message_text=(
                        message.text
                        or ""
                    ),
                    chunk_similarity=(
                        similarity
                    ),
                )
            )

            candidates.append(
                _SemanticMessageCandidate(
                    message=message,
                    similarity=(
                        similarity
                    ),
                    ranking_score=(
                        rerank.ranking_score
                    ),
                    distance=(
                        strongest_match.distance
                    ),
                    chunk_id=(
                        chunk.id
                    ),
                    chunk_order=(
                        chunk.chunk_order
                    ),
                    chunk_message_count=(
                        chunk.message_count
                    ),
                    chunk_chat_name=(
                        chunk.chat_name
                    ),
                    embedding_id=(
                        embedding.id
                    ),
                    embedding_model=(
                        embedding.model
                    ),
                    embedding_dimensions=(
                        embedding.dimensions
                    ),
                )
            )

        # ------------------------------------------------------
        # Message-level reranking
        # ------------------------------------------------------

        candidates.sort(
            key=lambda candidate: (
                candidate.ranking_score,
                candidate.similarity,
            ),
            reverse=True,
        )

        candidates = candidates[
            :query.candidate_limit
        ]

        # ------------------------------------------------------
        # Unified hits
        # ------------------------------------------------------

        return [
            self._build_hit(
                candidate
            )
            for candidate in candidates
        ]

    # ==========================================================
    # Message similarity
    # ==========================================================

    def _message_similarity(
        self,
        *,
        message: Message,
        chunk,
        similarity: float,
    ) -> float:
        """
        Convert chunk similarity into message similarity.

        Currently every source message inherits the semantic
        similarity of the strongest matching chunk.

        This is intentional.

        We do NOT invent artificial positional relevance until
        a separate message-level reranker exists.
        """

        _ = message
        _ = chunk

        return max(
            0.0,
            min(
                1.0,
                float(
                    similarity
                ),
            ),
        )

    # ==========================================================
    # Hit conversion
    # ==========================================================

    def _build_hit(
        self,
        candidate: _SemanticMessageCandidate,
    ) -> InvestigationSearchHit:
        """
        Convert semantic message candidate into unified hit.
        """

        message = (
            candidate.message
        )

        title = (
            self._build_title(
                message
            )
        )

        hit = (
            InvestigationSearchHit(
                object_id=message.id,
                object_type="message",
                case_id=message.case_id,
                title=title,
                snippet=(
                    self._build_snippet(
                        message
                    )
                ),
                scores=SearchScores(
                    semantic=(
                        candidate.similarity
                    ),
                ),
                matched_methods=[
                    SearchMethod.SEMANTIC,
                ],
                source=message,
                metadata={
                    "semantic_source": (
                        "conversation_chunk"
                    ),
                    "semantic_chunk_id": str(
                        candidate.chunk_id
                    ),
                    "semantic_chunk_order": (
                        candidate.chunk_order
                    ),
                    "semantic_chunk_message_count": (
                        candidate.chunk_message_count
                    ),
                    "semantic_chunk_chat_name": (
                        candidate.chunk_chat_name
                    ),
                    "semantic_chunk_embedding_id": str(
                        candidate.embedding_id
                    ),
                    "embedding_model": (
                        candidate.embedding_model
                    ),
                    "embedding_dimensions": (
                        candidate.embedding_dimensions
                    ),
                    "cosine_distance": (
                        candidate.distance
                    ),
                    "cosine_similarity": (
                        candidate.similarity
                    ),
                    "semantic_message_ranking_score": (
                        candidate.ranking_score
                    ),
                },
            )
        )

        hit.add_reason(
            SearchMatchReason(
                reason=(
                    self._build_reason(
                        candidate.similarity
                    )
                ),
                method=(
                    SearchMethod.SEMANTIC
                ),
                score=(
                    candidate.similarity
                ),
                details={
                    "semantic_source": (
                        "conversation_chunk"
                    ),
                    "chunk_id": str(
                        candidate.chunk_id
                    ),
                    "chunk_order": (
                        candidate.chunk_order
                    ),
                    "chunk_message_count": (
                        candidate.chunk_message_count
                    ),
                    "chat_name": (
                        candidate.chunk_chat_name
                    ),
                    "cosine_distance": (
                        candidate.distance
                    ),
                    "cosine_similarity": (
                        candidate.similarity
                    ),
                    "model": (
                        candidate.embedding_model
                    ),
                },
            )
        )

        return hit

    # ==========================================================
    # Explanation
    # ==========================================================

    @staticmethod
    def _build_reason(
        similarity: float,
    ) -> str:
        """
        Build readable semantic explanation.
        """

        if similarity >= 0.85:

            return (
                "Message belongs to a conversation "
                "segment with very strong semantic "
                "similarity."
            )

        if similarity >= 0.70:

            return (
                "Message belongs to a conversation "
                "segment with strong semantic "
                "similarity."
            )

        if similarity >= 0.50:

            return (
                "Message belongs to a conversation "
                "segment with moderate semantic "
                "similarity."
            )

        return (
            "Message belongs to a conversation "
            "segment with weak semantic similarity."
        )

    # ==========================================================
    # Title
    # ==========================================================

    @staticmethod
    def _build_title(
        message: Message,
    ) -> str:
        """
        Build compact Message hit title.
        """

        sender = (
            message.sender
            or ""
        ).strip()

        chat_name = (
            message.chat_name
            or ""
        ).strip()

        if (
            sender
            and chat_name
        ):

            return (
                f"{sender} — {chat_name}"
            )

        if sender:

            return sender

        if chat_name:

            return chat_name

        return "Message"

    # ==========================================================
    # Snippet
    # ==========================================================

    @staticmethod
    def _build_snippet(
        message: Message,
        *,
        maximum_length: int = 240,
    ) -> str:
        """
        Build compact Message snippet.
        """

        text = (
            message.text
            or ""
        ).strip()

        if not text:

            return ""

        if len(
            text
        ) <= maximum_length:

            return text

        return (
            text[
                :maximum_length
            ]
            .rstrip()
            + "..."
        )