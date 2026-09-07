"""
Search embedding repository.

Persistence and vector retrieval layer for semantic search.

Architecture:

EmbeddingService
      ↓
SearchEmbeddingRepository
      ↓
PostgreSQL + pgvector
      ↓
SemanticSearchRetriever

Responsibilities:

- create or update search embeddings
- find embedding by search index and model
- delete stale embeddings
- list embeddings for one case
- perform nearest-neighbour vector search
- keep semantic search scoped to investigation case

Does NOT:

- generate embeddings
- know about Ollama
- perform rank fusion
- perform query expansion
- interact with UI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.search_embedding import (
    SearchEmbedding,
)


@dataclass(
    slots=True,
)
class SemanticVectorMatch:
    """
    One pgvector nearest-neighbour result.

    distance:
        cosine distance returned by pgvector

    similarity:
        normalized cosine similarity calculated as:

            1 - distance
    """

    embedding: SearchEmbedding

    distance: float

    similarity: float


class SearchEmbeddingRepository:
    """
    Repository for semantic search embeddings.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

    # ==========================================================
    # Basic retrieval
    # ==========================================================

    def get_by_id(
        self,
        embedding_id: UUID,
    ) -> SearchEmbedding | None:
        """
        Return embedding by primary key.
        """

        statement = (
            select(
                SearchEmbedding
            )
            .where(
                SearchEmbedding.id
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

    def get_by_search_index(
        self,
        *,
        search_index_id: UUID,
        model: str,
    ) -> SearchEmbedding | None:
        """
        Return embedding generated for one SearchIndex
        by a specific model.
        """

        statement = (
            select(
                SearchEmbedding
            )
            .where(
                SearchEmbedding.search_index_id
                == search_index_id
            )
            .where(
                SearchEmbedding.model
                == model
            )
        )

        return (
            self.session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

    def get_by_case(
        self,
        *,
        case_id: UUID,
        model: str | None = None,
    ) -> list[
        SearchEmbedding
    ]:
        """
        Return embeddings belonging to one case.
        """

        statement = (
            select(
                SearchEmbedding
            )
            .where(
                SearchEmbedding.case_id
                == case_id
            )
        )

        if model is not None:

            statement = (
                statement.where(
                    SearchEmbedding.model
                    == model
                )
            )

        statement = (
            statement.order_by(
                SearchEmbedding.created_at
            )
        )

        return list(
            self.session
            .execute(
                statement
            )
            .scalars()
            .all()
        )

    # ==========================================================
    # Create / update
    # ==========================================================

    def upsert(
        self,
        *,
        case_id: UUID,
        search_index_id: UUID,
        object_id: UUID,
        object_type: str,
        model: str,
        vector: Sequence[
            float
        ],
    ) -> SearchEmbedding:
        """
        Create or update an embedding for one search index.

        Uniqueness is defined by:

            search_index_id + model
        """

        normalized_model = (
            model.strip()
        )

        normalized_object_type = (
            object_type
            .strip()
            .lower()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        if not normalized_object_type:

            raise ValueError(
                "Embedding object_type "
                "cannot be empty."
            )

        numeric_vector = [
            float(
                value
            )
            for value in vector
        ]

        if not numeric_vector:

            raise ValueError(
                "Embedding vector cannot be empty."
            )

        dimensions = len(
            numeric_vector
        )

        if dimensions != 768:

            raise ValueError(
                "Search embedding must contain "
                f"768 dimensions, got {dimensions}."
            )

        existing = (
            self.get_by_search_index(
                search_index_id=(
                    search_index_id
                ),
                model=(
                    normalized_model
                ),
            )
        )

        if existing is None:

            existing = SearchEmbedding(
                case_id=case_id,
                search_index_id=(
                    search_index_id
                ),
                object_id=object_id,
                object_type=(
                    normalized_object_type
                ),
                model=(
                    normalized_model
                ),
                dimensions=dimensions,
                embedding=(
                    numeric_vector
                ),
            )

            self.session.add(
                existing
            )

        else:

            existing.case_id = (
                case_id
            )

            existing.object_id = (
                object_id
            )

            existing.object_type = (
                normalized_object_type
            )

            existing.dimensions = (
                dimensions
            )

            existing.embedding = (
                numeric_vector
            )

        self.session.flush()

        return existing

    # ==========================================================
    # Delete
    # ==========================================================

    def delete_for_search_index(
        self,
        *,
        search_index_id: UUID,
        model: str | None = None,
    ) -> int:
        """
        Delete embeddings belonging to one SearchIndex.

        Returns number of deleted rows when available.
        """

        statement = (
            delete(
                SearchEmbedding
            )
            .where(
                SearchEmbedding.search_index_id
                == search_index_id
            )
        )

        if model is not None:

            statement = (
                statement.where(
                    SearchEmbedding.model
                    == model
                )
            )

        result = (
            self.session.execute(
                statement
            )
        )

        return int(
            result.rowcount
            or 0
        )

    def delete_for_case(
        self,
        *,
        case_id: UUID,
        model: str | None = None,
    ) -> int:
        """
        Delete semantic embeddings for one case.
        """

        statement = (
            delete(
                SearchEmbedding
            )
            .where(
                SearchEmbedding.case_id
                == case_id
            )
        )

        if model is not None:

            statement = (
                statement.where(
                    SearchEmbedding.model
                    == model
                )
            )

        result = (
            self.session.execute(
                statement
            )
        )

        return int(
            result.rowcount
            or 0
        )

    # ==========================================================
    # Vector search
    # ==========================================================

    def search_similar(
        self,
        *,
        case_id: UUID,
        model: str,
        query_vector: Sequence[
            float
        ],
        limit: int = 50,
        object_types: Sequence[
            str
        ] | None = None,
        object_ids: Sequence[
            UUID
        ] | None = None,
    ) -> list[
        SemanticVectorMatch
    ]:
        """
        Perform pgvector cosine nearest-neighbour search.

        PostgreSQL performs the vector-distance
        calculation instead of Python.

        Smaller cosine distance is better.

        similarity is derived as:

            1 - distance
        """

        if limit < 1:

            raise ValueError(
                "Semantic search limit must "
                "be at least 1."
            )

        normalized_model = (
            model.strip()
        )

        if not normalized_model:

            raise ValueError(
                "Embedding model cannot be empty."
            )

        vector = [
            float(
                value
            )
            for value in query_vector
        ]

        if len(
            vector
        ) != 768:

            raise ValueError(
                "Semantic query vector must contain "
                f"768 dimensions, got {len(vector)}."
            )

        distance_expression = (
            SearchEmbedding.embedding
            .cosine_distance(
                vector
            )
        )

        statement = (
            select(
                SearchEmbedding,
                distance_expression.label(
                    "distance"
                ),
            )
            .where(
                SearchEmbedding.case_id
                == case_id
            )
            .where(
                SearchEmbedding.model
                == normalized_model
            )
        )

        # ------------------------------------------------------
        # Object type scope
        # ------------------------------------------------------

        if object_types:

            normalized_types = [
                value
                .strip()
                .lower()

                for value
                in object_types

                if value
                and value.strip()
            ]

            if normalized_types:

                statement = (
                    statement.where(
                        SearchEmbedding.object_type
                        .in_(
                            normalized_types
                        )
                    )
                )

        # ------------------------------------------------------
        # Explicit object IDs
        # ------------------------------------------------------

        if object_ids:

            ids = list(
                object_ids
            )

            if ids:

                statement = (
                    statement.where(
                        SearchEmbedding.object_id
                        .in_(
                            ids
                        )
                    )
                )

        statement = (
            statement
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

        matches: list[
            SemanticVectorMatch
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

            similarity = min(
                1.0,
                max(
                    0.0,
                    similarity,
                ),
            )

            matches.append(
                SemanticVectorMatch(
                    embedding=embedding,
                    distance=(
                        numeric_distance
                    ),
                    similarity=(
                        similarity
                    ),
                )
            )

        return matches

    # ==========================================================
    # Counts
    # ==========================================================

    def count_for_case(
        self,
        *,
        case_id: UUID,
        model: str | None = None,
    ) -> int:
        """
        Return number of stored embeddings for one case.
        """

        embeddings = (
            self.get_by_case(
                case_id=case_id,
                model=model,
            )
        )

        return len(
            embeddings
        )

    def get_existing_search_index_ids(
        self,
        *,
        case_id: UUID,
        model: str,
    ) -> set[UUID]:
        """
        Return SearchIndex IDs that already have an embedding
        for the requested case/model.

        This method intentionally selects only search_index_id.

        It avoids loading:

        - VECTOR(768) values
        - SearchIndex relationships
        - Case relationships
        - ORM SearchEmbedding instances

        Intended for high-volume embedding backfills.
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
                SearchEmbedding.search_index_id
            )
            .where(
                SearchEmbedding.case_id
                == case_id
            )
            .where(
                SearchEmbedding.model
                == normalized_model
            )
        )

        rows = (
            self.session
            .execute(
                statement
            )
            .scalars()
            .all()
        )

        return set(
            rows
        )