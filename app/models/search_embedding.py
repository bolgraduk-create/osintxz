"""
Search embedding model.

Stores vector representations used by semantic search.

Architecture:

SearchIndex
    ↓
SearchEmbedding
    ↓
pgvector
    ↓
SemanticSearchRetriever

Responsibilities:

- store one vector representation of a search object
- associate embedding with case/object/search index
- preserve embedding model metadata
- support future embedding re-generation

Does NOT:

- generate embeddings
- perform semantic search
- calculate cosine similarity in Python
- perform rank fusion
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import BaseModel
from app.database.mixins import (
    TimestampMixin,
)


if TYPE_CHECKING:

    from app.models.case import Case

    from app.models.search_index import SearchIndex


class SearchEmbedding(
    BaseModel,
    TimestampMixin,
):
    """
    Vector representation of one searchable object.

    Current embedding model:

        nomic-embed-text

    Current dimensions:

        768

    The model name is stored explicitly so embeddings
    can be invalidated or regenerated if the embedding
    provider changes in the future.
    """

    __tablename__ = (
        "search_embeddings"
    )

    __table_args__ = (
        UniqueConstraint(
            "search_index_id",
            "model",
            name=(
                "uq_search_embedding_"
                "index_model"
            ),
        ),
    )

    # ==========================================================
    # Investigation scope
    # ==========================================================

    case_id: Mapped[
        UUID
    ] = mapped_column(
        UUID(
            as_uuid=True
        ),
        ForeignKey(
            "cases.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Search index source
    # ==========================================================

    search_index_id: Mapped[
        UUID
    ] = mapped_column(
        UUID(
            as_uuid=True
        ),
        ForeignKey(
            "search_indexes.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Original object identity
    # ==========================================================

    object_id: Mapped[
        UUID
    ] = mapped_column(
        UUID(
            as_uuid=True
        ),
        nullable=False,
        index=True,
    )

    object_type: Mapped[
        str
    ] = mapped_column(
        String(
            64
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Embedding metadata
    # ==========================================================

    model: Mapped[
        str
    ] = mapped_column(
        String(
            128
        ),
        nullable=False,
        index=True,
    )

    dimensions: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=768,
    )

    # ==========================================================
    # Vector
    # ==========================================================

    embedding: Mapped[
        list[
            float
        ]
    ] = mapped_column(
        Vector(
            768
        ),
        nullable=False,
    )

    # ==========================================================
    # Relationships
    # ==========================================================

    case: Mapped[
        "Case"
    ] = relationship(
        "Case",
        lazy="joined",
    )

    search_index: Mapped[
        "SearchIndex"
    ] = relationship(
        "SearchIndex",
        lazy="joined",
    )

    # ==========================================================
    # Helpers
    # ==========================================================

    def matches_model(
        self,
        model_name: str,
    ) -> bool:
        """
        Check whether embedding was generated
        by the requested model.
        """

        return (
            self.model
            == model_name
        )

    @property
    def vector_dimensions(
        self,
    ) -> int:
        """
        Return stored vector dimension metadata.
        """

        return self.dimensions