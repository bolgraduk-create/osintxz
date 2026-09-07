"""
Semantic chunk embedding model.

Stores vector representations for SearchSemanticChunk.

Architecture:

SearchSemanticChunk
        ↓
SearchSemanticChunkEmbedding
        ↓
pgvector
        ↓
SemanticChunkRetriever

Responsibilities:

- store one vector per semantic chunk/model
- preserve chunk content hash used for stale detection
- support future model migration
- support pgvector nearest-neighbour search

Does NOT:

- build chunks
- generate embeddings
- perform retrieval orchestration
- perform rank fusion
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import (
    BaseModel,
)

from app.database.mixins import (
    TimestampMixin,
)


if TYPE_CHECKING:

    from app.models.case import (
        Case,
    )

    from app.models.search_semantic_chunk import (
        SearchSemanticChunk,
    )


class SearchSemanticChunkEmbedding(
    BaseModel,
    TimestampMixin,
):
    """
    Vector representation of one semantic chunk.
    """

    __tablename__ = (
        "search_semantic_chunk_embeddings"
    )

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "model",
            name=(
                "uq_search_semantic_chunk_"
                "embedding_chunk_model"
            ),
        ),
    )

    # ==========================================================
    # Investigation scope
    # ==========================================================

    case_id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
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
    # Chunk reference
    # ==========================================================

    chunk_id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        ForeignKey(
            "search_semantic_chunks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ==========================================================
    # Stale detection
    # ==========================================================

    content_hash: Mapped[
        str
    ] = mapped_column(
        String(
            64
        ),
        nullable=False,
        index=True,
    )

    """
    Hash of chunk text at the moment this vector
    was generated.

    If:

        embedding.content_hash
        != chunk.content_hash

    the vector is stale.
    """

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
        list[float]
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

    chunk: Mapped[
        "SearchSemanticChunk"
    ] = relationship(
        "SearchSemanticChunk",
        lazy="joined",
    )

    # ==========================================================
    # Helpers
    # ==========================================================

    def is_stale(
        self,
        chunk: "SearchSemanticChunk",
    ) -> bool:
        """
        Check whether this vector represents the
        current version of the chunk.
        """

        return (
            self.content_hash
            != chunk.content_hash
        )

    def matches_model(
        self,
        model_name: str,
    ) -> bool:
        """
        Check embedding model.
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
        Return vector dimension metadata.
        """

        return self.dimensions