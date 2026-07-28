"""
Message repository.

Provides database operations
for imported messages.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message

from app.repositories.base_repository import (
    BaseRepository,
)


class MessageRepository(
    BaseRepository[Message],
):
    """
    Repository for Message model.
    """

    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            Message,
        )


    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[Message]:
        """
        Return messages belonging to a case.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.case_id == case_id
            )
            .order_by(
                Message.sent_at
            )
        )

        return list(
            result.scalars().all()
        )


    def get_by_source(
        self,
        source_id: UUID,
    ) -> list[Message]:
        """
        Return messages from source.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.source_id == source_id
            )
            .order_by(
                Message.sent_at
            )
        )

        return list(
            result.scalars().all()
        )


    def find_by_sender(
        self,
        sender: str,
    ) -> list[Message]:
        """
        Find messages by sender.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.sender == sender
            )
            .order_by(
                Message.sent_at
            )
        )

        return list(
            result.scalars().all()
        )


    def search_text(
        self,
        text: str,
    ) -> list[Message]:
        """
        Search messages by text content.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.text.ilike(
                    f"%{text}%"
                )
            )
        )

        return list(
            result.scalars().all()
        )


    def get_between_dates(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Message]:
        """
        Return messages inside time range.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.sent_at >= start,
                Message.sent_at <= end,
            )
            .order_by(
                Message.sent_at
            )
        )

        return list(
            result.scalars().all()
        )


    def get_chat_messages(
        self,
        chat_name: str,
    ) -> list[Message]:
        """
        Return all messages from chat.
        """

        result = self.session.execute(
            select(Message)
            .where(
                Message.chat_name == chat_name
            )
            .order_by(
                Message.sent_at
            )
        )

        return list(
            result.scalars().all()
        )