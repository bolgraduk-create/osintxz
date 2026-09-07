"""
Search semantic chunk repository.

Persistence layer for SearchSemanticChunk.

Responsibilities:

- create semantic chunks
- retrieve chunks by id
- retrieve chunks by case
- retrieve chunks by source
- retrieve chunks by chat
- find deterministic chunk by chunk_key
- update existing chunks
- delete stale chunks during rebuild

Does NOT:

- build message chunks
- generate embeddings
- perform semantic search
- perform rank fusion
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from app.models.search_semantic_chunk import (
    SearchSemanticChunk,
)


class SearchSemanticChunkRepository:
    """
    Repository for semantic search chunks.
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
        chunk: SearchSemanticChunk,
    ) -> SearchSemanticChunk:
        """
        Persist a semantic chunk.
        """

        self.session.add(
            chunk
        )

        self.session.flush()

        return chunk

    # ==========================================================
    # Get by ID
    # ==========================================================

    def get(
        self,
        chunk_id: UUID,
    ) -> SearchSemanticChunk | None:
        """
        Return semantic chunk by primary key.
        """

        statement = (
            select(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.id
                == chunk_id
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
    # Deterministic lookup
    # ==========================================================

    def get_by_key(
        self,
        *,
        case_id: UUID,
        chunk_key: str,
    ) -> SearchSemanticChunk | None:
        """
        Find chunk using deterministic chunk key.
        """

        statement = (
            select(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
            )
            .where(
                SearchSemanticChunk.chunk_key
                == chunk_key
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
    # Case
    # ==========================================================

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[SearchSemanticChunk]:
        """
        Return all semantic chunks belonging to a case.

        Results are returned in deterministic conversation
        order where possible.
        """

        statement = (
            select(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
            )
            .order_by(
                SearchSemanticChunk.source_id,
                SearchSemanticChunk.chat_name,
                SearchSemanticChunk.chunk_order,
                SearchSemanticChunk.started_at,
                SearchSemanticChunk.id,
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
    # Source
    # ==========================================================

    def get_by_source(
        self,
        *,
        case_id: UUID,
        source_id: UUID,
    ) -> list[SearchSemanticChunk]:
        """
        Return chunks belonging to one source.
        """

        statement = (
            select(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
            )
            .where(
                SearchSemanticChunk.source_id
                == source_id
            )
            .order_by(
                SearchSemanticChunk.chat_name,
                SearchSemanticChunk.chunk_order,
                SearchSemanticChunk.started_at,
                SearchSemanticChunk.id,
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
    # Chat
    # ==========================================================

    def get_by_chat(
        self,
        *,
        case_id: UUID,
        chat_name: str,
    ) -> list[SearchSemanticChunk]:
        """
        Return chunks belonging to one chat.
        """

        statement = (
            select(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
            )
            .where(
                SearchSemanticChunk.chat_name
                == chat_name
            )
            .order_by(
                SearchSemanticChunk.chunk_order,
                SearchSemanticChunk.started_at,
                SearchSemanticChunk.id,
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
    # Existing keys
    # ==========================================================

    def get_keys_by_case(
        self,
        case_id: UUID,
    ) -> set[str]:
        """
        Return only chunk keys for a case.

        Lightweight method intended for large rebuilds.
        """

        statement = (
            select(
                SearchSemanticChunk.chunk_key
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
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
    # Update
    # ==========================================================

    def update(
        self,
        chunk: SearchSemanticChunk,
    ) -> SearchSemanticChunk:
        """
        Flush changes to an existing chunk.
        """

        self.session.add(
            chunk
        )

        self.session.flush()

        return chunk

    # ==========================================================
    # Delete
    # ==========================================================

    def delete(
        self,
        chunk: SearchSemanticChunk,
    ) -> None:
        """
        Delete one semantic chunk.

        Embeddings are removed automatically through
        the database ON DELETE CASCADE relationship.
        """

        self.session.delete(
            chunk
        )

        self.session.flush()

    # ==========================================================
    # Delete case chunks
    # ==========================================================

    def delete_by_case(
        self,
        case_id: UUID,
    ) -> int:
        """
        Delete every semantic chunk belonging to a case.

        Intended primarily for explicit full rebuilds.
        """

        statement = (
            delete(
                SearchSemanticChunk
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
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
    # Count
    # ==========================================================

    def count_by_case(
        self,
        case_id: UUID,
    ) -> int:
        """
        Return number of semantic chunks in a case.
        """

        statement = (
            select(
                SearchSemanticChunk.id
            )
            .where(
                SearchSemanticChunk.case_id
                == case_id
            )
        )

        return len(
            self.session
            .execute(
                statement
            )
            .scalars()
            .all()
        )