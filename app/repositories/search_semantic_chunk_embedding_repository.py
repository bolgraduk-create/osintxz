"""
Search semantic chunk embedding repository.

Persistence and vector retrieval layer for
SearchSemanticChunkEmbedding.

Optimized for large semantic indexes.

Responsibilities:

- create chunk embeddings
- retrieve individual embeddings
- retrieve lightweight embedding state
- detect existing/stale chunk embeddings without loading vectors
- perform pgvector cosine similarity search
- delete embeddings
- support bulk semantic indexing

Does NOT:

- generate embeddings
- build message chunks
- orchestrate unified search
- perform rank fusion
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.models.search_semantic_chunk import (
    SearchSemanticChunk,
)

from app.models.search_semantic_chunk_embedding import (
    SearchSemanticChunkEmbedding,
)


# ==========================================================
# Lightweight state
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class SemanticChunkEmbeddingState:
    """
    Lightweight state of an existing chunk embedding.

    Vector data is intentionally not loaded.
    """

    chunk_id: UUID

    content_hash: str


# ==========================================================
# Similarity result
# ==========================================================

@dataclass(
    frozen=True,
    slots=True,
)
class SemanticChunkSimilarityResult:
    """
    One semantic chunk similarity result.
    """

    embedding: SearchSemanticChunkEmbedding

    distance: float

    similarity: float


class SearchSemanticChunkEmbeddingRepository:
    """
    Repository for semantic chunk embeddings.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

    # ==========================================================
    # Create
    # ==========================================================

    def create(
        self,
        embedding: SearchSemanticChunkEmbedding,
    ) -> SearchSemanticChunkEmbedding:
        """
        Persist one chunk embedding.
        """

        self.session.add(
            embedding
        )

        self.session.flush()

        return embedding

    # ==========================================================
    # Get by ID
    # ==========================================================

    def get(
        self,
        embedding_id: UUID,
    ) -> SearchSemanticChunkEmbedding | None:
        """
        Return embedding by primary key.
        """

        statement = (
            select(
                SearchSemanticChunkEmbedding
            )
            .where(
                SearchSemanticChunkEmbedding.id
                == embedding_id
            )
        )

        return (
            self.session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

    # ==========================================================
    # Get chunk/model
    # ==========================================================

    def get_by_chunk(
        self,
        *,
        chunk_id: UUID,
        model: str,
    ) -> SearchSemanticChunkEmbedding | None:
        """
        Return embedding for one chunk/model.
        """

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        statement = (
            select(
                SearchSemanticChunkEmbedding
            )
            .where(
                SearchSemanticChunkEmbedding.chunk_id
                == chunk_id
            )
            .where(
                SearchSemanticChunkEmbedding.model
                == normalized_model
            )
        )

        return (
            self.session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

    # ==========================================================
    # Lightweight bulk state
    # ==========================================================

    def get_states_by_case(
        self,
        *,
        case_id: UUID,
        model: str,
    ) -> dict[
        UUID,
        SemanticChunkEmbeddingState,
    ]:
        """
        Return existing embedding state for a case/model.

        IMPORTANT:

        Only chunk_id and content_hash are selected.

        VECTOR(768), Case and SearchSemanticChunk ORM
        relationships are not loaded.

        This prevents the expensive preload problem that
        existed in the original SearchEmbedding pipeline.
        """

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        statement = (
            select(
                SearchSemanticChunkEmbedding.chunk_id,
                SearchSemanticChunkEmbedding.content_hash,
            )
            .where(
                SearchSemanticChunkEmbedding.case_id
                == case_id
            )
            .where(
                SearchSemanticChunkEmbedding.model
                == normalized_model
            )
        )

        rows = (
            self.session
            .execute(
                statement
            )
            .all()
        )

        return {
            chunk_id: (
                SemanticChunkEmbeddingState(
                    chunk_id=chunk_id,
                    content_hash=content_hash,
                )
            )
            for (
                chunk_id,
                content_hash,
            )
            in rows
        }

    # ==========================================================
    # Existing chunk IDs
    # ==========================================================

    def get_existing_chunk_ids(
        self,
        *,
        case_id: UUID,
        model: str,
    ) -> set[UUID]:
        """
        Return IDs of chunks with existing embeddings.

        Vector values are not loaded.
        """

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        statement = (
            select(
                SearchSemanticChunkEmbedding.chunk_id
            )
            .where(
                SearchSemanticChunkEmbedding.case_id
                == case_id
            )
            .where(
                SearchSemanticChunkEmbedding.model
                == normalized_model
            )
        )

        return set(
            self.session
            .execute(
                statement
            )
            .scalars()
            .all()
        )

    # ==========================================================
    # Similarity search
    # ==========================================================

    def search_similar(
        self,
        *,
        case_id: UUID,
        query_vector: list[float] | tuple[float, ...],
        model: str,
        limit: int = 20,
    ) -> list[
        SemanticChunkSimilarityResult
    ]:
        """
        Find semantic chunks using cosine distance.

        Cosine similarity is calculated as:

            similarity = 1 - cosine_distance

        Only embeddings belonging to the requested case
        and model participate in retrieval.
        """

        if limit < 1:

            return []

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        vector = list(
            query_vector
        )

        if not vector:

            return []

        distance_expression = (
            SearchSemanticChunkEmbedding
            .embedding
            .cosine_distance(
                vector
            )
        )

        statement = (
            select(
                SearchSemanticChunkEmbedding,
                distance_expression.label(
                    "distance"
                ),
            )
            .options(
                joinedload(
                    SearchSemanticChunkEmbedding.chunk
                )
            )
            .where(
                SearchSemanticChunkEmbedding.case_id
                == case_id
            )
            .where(
                SearchSemanticChunkEmbedding.model
                == normalized_model
            )
            .order_by(
                distance_expression
            )
            .limit(
                limit
            )
        )

        rows = (
            self.session
            .execute(
                statement
            )
            .all()
        )

        results: list[
            SemanticChunkSimilarityResult
        ] = []

        for (
            embedding,
            distance,
        ) in rows:

            numeric_distance = float(
                distance
            )

            similarity = (
                1.0
                - numeric_distance
            )

            results.append(
                SemanticChunkSimilarityResult(
                    embedding=embedding,
                    distance=numeric_distance,
                    similarity=similarity,
                )
            )

        return results

    # ==========================================================
    # Update
    # ==========================================================

    def update(
        self,
        embedding: SearchSemanticChunkEmbedding,
    ) -> SearchSemanticChunkEmbedding:
        """
        Flush modifications to an existing embedding.
        """

        self.session.add(
            embedding
        )

        self.session.flush()

        return embedding

    # ==========================================================
    # Delete one
    # ==========================================================

    def delete(
        self,
        embedding: SearchSemanticChunkEmbedding,
    ) -> None:
        """
        Delete one chunk embedding.
        """

        self.session.delete(
            embedding
        )

        self.session.flush()

    # ==========================================================
    # Delete by chunk
    # ==========================================================

    def delete_by_chunk(
        self,
        chunk_id: UUID,
    ) -> int:
        """
        Delete all embeddings belonging to one chunk.
        """

        statement = (
            delete(
                SearchSemanticChunkEmbedding
            )
            .where(
                SearchSemanticChunkEmbedding.chunk_id
                == chunk_id
            )
        )

        result = (
            self.session
            .execute(
                statement
            )
        )

        self.session.flush()

        return int(
            result.rowcount
            or 0
        )

    # ==========================================================
    # Delete by case/model
    # ==========================================================

    def delete_by_case(
        self,
        *,
        case_id: UUID,
        model: str | None = None,
    ) -> int:
        """
        Delete semantic chunk embeddings for a case.

        If model is supplied, only that model is removed.
        """

        statement = (
            delete(
                SearchSemanticChunkEmbedding
            )
            .where(
                SearchSemanticChunkEmbedding.case_id
                == case_id
            )
        )

        if model is not None:

            normalized_model = (
                model.strip()
            )

            if not normalized_model:

                raise ValueError(
                    "Embedding model cannot be empty."
                )

            statement = (
                statement.where(
                    SearchSemanticChunkEmbedding.model
                    == normalized_model
                )
            )

        result = (
            self.session
            .execute(
                statement
            )
        )

        self.session.flush()

        return int(
            result.rowcount
            or 0
        )