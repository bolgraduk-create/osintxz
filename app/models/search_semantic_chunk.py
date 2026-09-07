"""
Semantic search chunk model.

Represents a compact semantic unit built from a sequence
of related investigation messages.

Architecture:

Message[]
    ↓
MessageSemanticChunkBuilder
    ↓
SearchSemanticChunk
    ↓
SearchSemanticChunkEmbedding
    ↓
pgvector
    ↓
SemanticChunkRetriever
    ↓
candidate Message[]
    ↓
UnifiedSearchService

A chunk does NOT replace SearchIndex.

SearchIndex remains the canonical lexical/fuzzy searchable
representation of individual investigation objects.

Chunks are an optimization layer for semantic retrieval over
large message collections.

Responsibilities:

- group related messages into one semantic unit
- preserve links to source Message IDs
- preserve chat/source/time context
- support deterministic rebuilding
- support stale-content detection through content_hash
- provide text for semantic embedding

Does NOT:

- generate embeddings
- perform semantic search
- perform rank fusion
- replace Message
- replace SearchIndex
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
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

    from app.models.source import (
        Source,
    )


class SearchSemanticChunk(
    BaseModel,
    TimestampMixin,
):
    """
    Semantic message chunk.

    One row represents several chronologically related
    messages belonging to the same investigation context.

    The actual embedding is stored separately so chunk
    lifecycle and embedding lifecycle remain independent.
    """

    __tablename__ = (
        "search_semantic_chunks"
    )

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "chunk_key",
            name=(
                "uq_search_semantic_chunk_"
                "case_key"
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
    # Source scope
    # ==========================================================

    source_id: Mapped[
        UUID | None
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        ForeignKey(
            "sources.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # ==========================================================
    # Deterministic identity
    # ==========================================================

    chunk_key: Mapped[
        str
    ] = mapped_column(
        String(
            128
        ),
        nullable=False,
        index=True,
    )

    """
    Deterministic chunk identity.

    The builder will calculate this value from stable chunk
    properties such as ordered Message IDs.

    Rebuilding the same chunk therefore updates the existing
    row instead of creating another one.
    """

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
    SHA256 of semantic chunk content.

    Used later to determine whether an existing vector is
    stale and must be regenerated.
    """

    # ==========================================================
    # Conversation context
    # ==========================================================

    chat_name: Mapped[
        str | None
    ] = mapped_column(
        String(
            255
        ),
        nullable=True,
        index=True,
    )

    chunk_order: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    """
    Position of this chunk inside its source/chat sequence.

    This is useful for neighboring-chunk expansion later.
    """

    # ==========================================================
    # Time range
    # ==========================================================

    started_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        index=True,
    )

    ended_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        index=True,
    )

    # ==========================================================
    # Message references
    # ==========================================================

    message_count: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    message_ids: Mapped[
        list[str]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    """
    Ordered Message IDs represented by this chunk.

    UUID values are intentionally stored as strings inside
    JSONB so the ordered collection remains portable and easy
    to serialize.

    Message rows themselves remain the source of truth.
    """

    # ==========================================================
    # Semantic content
    # ==========================================================

    text: Mapped[
        str
    ] = mapped_column(
        Text,
        nullable=False,
    )

    """
    Combined human-readable semantic representation.

    Example:

        John:
        Are we meeting tomorrow?

        Mark:
        Yes, around six.

        John:
        Send me the address.

    Technical UUIDs, raw JSON metadata and other low-value
    fields should not be included here.
    """

    # ==========================================================
    # Relationships
    # ==========================================================

    case: Mapped[
        "Case"
    ] = relationship(
        "Case",
        lazy="joined",
    )

    source: Mapped[
        "Source | None"
    ] = relationship(
        "Source",
        lazy="joined",
    )

    # ==========================================================
    # Helpers
    # ==========================================================

    @property
    def has_messages(
        self,
    ) -> bool:
        """
        Return whether the chunk contains message references.
        """

        return bool(
            self.message_ids
        )

    @property
    def first_message_id(
        self,
    ) -> UUID | None:
        """
        Return first Message UUID when available.
        """

        if not self.message_ids:

            return None

        try:

            return UUID(
                self.message_ids[
                    0
                ]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @property
    def last_message_id(
        self,
    ) -> UUID | None:
        """
        Return last Message UUID when available.
        """

        if not self.message_ids:

            return None

        try:

            return UUID(
                self.message_ids[
                    -1
                ]
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    def contains_message(
        self,
        message_id: UUID,
    ) -> bool:
        """
        Check whether a Message belongs to this chunk.
        """

        return (
            str(
                message_id
            )
            in self.message_ids
        )