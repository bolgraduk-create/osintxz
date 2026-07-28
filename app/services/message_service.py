"""
Message service.

Contains business logic related
to imported messages.

Examples:

- Telegram messages
- WhatsApp messages
- Discord messages
- Emails
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.message import Message

from app.repositories.message_repository import (
    MessageRepository,
)


class MessageService:
    """
    Service for managing messages.
    """

    def __init__(
        self,
        session: Session,
    ):
        self.repository = MessageRepository(
            session
        )


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
    ) -> Message:
        """
        Create imported message.
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

        return self.repository.create(
            message
        )


    def get_message(
        self,
        message_id: UUID,
    ) -> Message | None:
        """
        Get message by id.
        """

        return self.repository.get(
            message_id
        )


    def get_case_messages(
        self,
        case_id: UUID,
    ) -> list[Message]:
        """
        Return messages belonging
        to a case.
        """

        return self.repository.get_by_case(
            case_id
        )


    def search_messages(
        self,
        text: str,
    ) -> list[Message]:
        """
        Search messages by text.
        """

        return self.repository.search_text(
            text
        )


    def get_sender_messages(
        self,
        sender: str,
    ) -> list[Message]:
        """
        Return messages from sender.
        """

        return self.repository.get_by_sender(
            sender
        )


    def delete_message(
        self,
        message_id: UUID,
    ) -> bool:
        """
        Soft delete message.
        """

        message = self.repository.get(
            message_id
        )

        if message is None:
            return False

        message.soft_delete()

        self.repository.session.flush()

        return True