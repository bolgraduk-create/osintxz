"""
Telegram collector.

Converts Telegram export into
CollectedItem objects.

Responsibilities:

- use TelegramParser
- convert messages
- return collected items

Does NOT:

- save to database
- create Evidence
- perform analysis
"""

from __future__ import annotations

from pathlib import Path

from app.collectors.base.models import (
    CollectedItem,
    CollectedItemType,
)

from .telegram_parser import TelegramParser


class TelegramCollector:
    """
    Telegram collection adapter.
    """

    def __init__(self) -> None:

        self.parser = TelegramParser()

    def collect(
        self,
        path: str | Path,
    ) -> list[CollectedItem]:
        """
        Collect Telegram data.
        """

        export = self.parser.parse(path)

        items: list[CollectedItem] = []

        for chat in export.chats:

            for message in chat.messages:

                items.append(
                    self._convert_message(
                        message,
                        chat,
                    )
                )

        return items
    def _convert_message(
        self,
        message,
        chat,
    ) -> CollectedItem:
        """
        Convert Telegram message
        into CollectedItem.
        """

        return CollectedItem(

            source="telegram",

            item_type=CollectedItemType.MESSAGE,

            content=message.text,

            timestamp=message.timestamp,

            title=chat.title,

            author=message.sender_name,

            external_id=str(message.id),

            metadata={

                "chat_id": chat.id,

                "chat_title": chat.title,

                "sender_id": message.sender_id,

                "reply_to": (
                    message.reply.message_id if message.reply else None
                ),

                "message_type": (
                    message.message_type.value
                    if getattr(message, "message_type", None)
                    else None
                ),

                "attachments": [
                    attachment.file_path for attachment in getattr(message, "attachments", [])
                ],

            },

        )