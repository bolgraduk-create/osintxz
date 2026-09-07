"""
Message service.

Contains business logic related
to imported messages.

Examples:

- Telegram messages
- WhatsApp messages
- Discord messages
- Emails

Search lifecycle:

Message
    ↓
MessageRepository
    ↓
SearchIndexingService
    ↓
SearchIndex

Semantic embeddings are intentionally deferred during
normal message ingestion so high-volume imports do not
perform one Ollama request per message.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import (
    Message,
)

from app.repositories.message_repository import (
    MessageRepository,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)


class MessageService:
    """
    Service for managing messages.
    """

    def __init__(
        self,
        session: Session,
        *,
        search_indexing_service: (
            SearchIndexingService
            | None
        ) = None,
    ) -> None:

        self.repository = (
            MessageRepository(
                session
            )
        )

        self.search_indexing_service = (
            search_indexing_service
        )

    # ======================================================
    # Create
    # ======================================================

    def create_message(
        self,
        case_id: UUID,
        source_id: UUID,
        text: str | None = None,
        sender: str | None = None,
        receiver: str | None = None,
        chat_name: str | None = None,
        sent_at: datetime | None = None,
        external_id: str | None = None,
        evidence_id: UUID | None = None,
        *,
        update_search_index: bool = True,
    ) -> Message:
        """
        Create imported message.

        SearchIndex is updated immediately.

        Semantic embedding generation is deferred and
        should normally be performed in batch after
        high-volume imports.
        """

        message = Message(
            case_id=case_id,
            source_id=source_id,
            evidence_id=evidence_id,
            external_id=external_id,
            sender=sender,
            receiver=receiver,
            chat_name=chat_name,
            sent_at=sent_at,
            text=text,
        )

        message = (
            self.repository.create(
                message
            )
        )

        # --------------------------------------------------
        # Search lifecycle
        # --------------------------------------------------

        if (
            update_search_index
            and self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .index_object_text_only(
                    message
                )

        return message

    # ======================================================
    # Get
    # ======================================================

    def get_message(
        self,
        message_id: UUID,
    ) -> Message | None:
        """
        Get message by id.
        """

        return (
            self.repository.get(
                message_id
            )
        )

    def get_case_messages(
        self,
        case_id: UUID,
    ) -> list[
        Message
    ]:
        """
        Return messages belonging to a case.
        """

        return (
            self.repository.get_by_case(
                case_id
            )
        )

    # ======================================================
    # Search
    # ======================================================

    def search_messages(
        self,
        text: str,
    ) -> list[
        Message
    ]:
        """
        Legacy direct message search.

        Unified application search should prefer
        UnifiedSearchService.
        """

        return (
            self.repository.search_text(
                text
            )
        )

    # ======================================================
    # Sender
    # ======================================================

    def get_sender_messages(
        self,
        sender: str,
    ) -> list[
        Message
    ]:
        """
        Return messages from sender.
        """

        return (
            self.repository.get_by_sender(
                sender
            )
        )

    # ======================================================
    # Explicit semantic refresh
    # ======================================================

    def refresh_search(
        self,
        message_id: UUID,
        *,
        include_embedding: bool = True,
    ) -> bool:
        """
        Refresh search representation for one message.

        Useful after message modification.
        """

        if (
            self.search_indexing_service
            is None
        ):

            return False

        message = (
            self.repository.get(
                message_id
            )
        )

        if message is None:

            return False

        self.search_indexing_service \
            .index_object(
                message,
                include_embedding=(
                    include_embedding
                ),
                force_embedding=(
                    include_embedding
                ),
            )

        return True

    # ======================================================
    # Delete
    # ======================================================

    def delete_message(
        self,
        message_id: UUID,
    ) -> bool:
        """
        Soft delete message.

        Search-index deletion will be connected once
        SearchIndexingService receives explicit
        deindex/remove lifecycle support.
        """

        message = (
            self.repository.get(
                message_id
            )
        )

        if message is None:

            return False

        message.soft_delete()

        self.repository.session.flush()

        if (
            self.search_indexing_service
            is not None
        ):

            self.search_indexing_service \
                .remove_object(
                    message
                )

        return True