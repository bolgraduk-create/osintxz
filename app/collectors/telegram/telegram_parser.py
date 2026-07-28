"""
Telegram export parser.

Converts Telegram JSON export into
domain Telegram models.

Responsibilities:

- load Telegram export
- parse chats
- parse users
- parse messages

Does NOT:

- save to database
- create Evidence
- perform AI analysis
"""

from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path
from typing import Any

from .telegram_models import (
    TelegramAttachment,
    TelegramChat,
    TelegramChatType,
    TelegramExport,
    TelegramMessage,
    TelegramMessageType,
    TelegramUser,
)


class TelegramParser:
    """
    Parses Telegram exports.
    """

    def parse(
        self,
        path: str | Path,
    ) -> TelegramExport:
        """
        Parse Telegram export.
        """

        path = Path(path)

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        export = TelegramExport(
            source=str(path),
        )

        chat = self._parse_chat(data)

        export.chats.append(chat)

        return export

    def _parse_chat(
        self,
        data: dict[str, Any],
    ) -> TelegramChat:
        """
        Parse single chat.
        """

        chat = TelegramChat()

        chat.id = str(
            data.get("id", "")
        )

        chat.title = data.get(
            "name",
            ""
        )

        chat.chat_type = (
            TelegramChatType.PRIVATE
        )

        messages = data.get(
            "messages",
            []
        )

        for raw in messages:

            message = self._parse_message(
                raw
            )

            chat.messages.append(
                message
            )

        return chat

    def _parse_message(
        self,
        data: dict[str, Any],
    ) -> TelegramMessage:
        """
        Parse Telegram message.
        """

        message = TelegramMessage(
            id=int(
                data.get(
                    "id",
                    0,
                )
            )
        )

        # -------------------------
        # Sender
        # -------------------------

        message.sender_name = (
            data.get("from")
        )

        message.sender_id = (
            data.get("from_id")
        )

        if (
            message.sender_name
            or message.sender_id
        ):

            message.sender = TelegramUser(

                id=message.sender_id,

                display_name=
                message.sender_name,

            )

        # -------------------------
        # Time
        # -------------------------

        date = data.get("date")

        if date:

            try:

                message.timestamp = (
                    datetime.fromisoformat(
                        date.replace(
                            "T",
                            " "
                        )
                    )
                )

            except Exception:

                message.timestamp = None

        # -------------------------
        # Text
        # -------------------------

        text = data.get(
            "text",
            "",
        )

        if isinstance(
            text,
            list,
        ):

            parts = []

            for item in text:

                if isinstance(
                    item,
                    str,
                ):

                    parts.append(
                        item
                    )

                elif isinstance(
                    item,
                    dict,
                ):

                    parts.append(
                        str(
                            item.get(
                                "text",
                                "",
                            )
                        )
                    )

            text = "".join(parts)

        message.text = str(text)

        message.raw_text = (
            message.text
        )

        message.normalized_text = (
            message.text.strip()
        )

        # -------------------------
        # Reply
        # -------------------------

        if (
            "reply_to_message_id"
            in data
        ):

            from .telegram_models import (
                TelegramReplyInfo,
            )

            message.reply = (
                TelegramReplyInfo(
                    message_id=data.get(
                        "reply_to_message_id"
                    )
                )
            )

        # -------------------------
        # Forward
        # -------------------------

        if (
            "forwarded_from"
            in data
        ):

            from .telegram_models import (
                TelegramForwardInfo,
            )

            message.forward = (
                TelegramForwardInfo(
                    from_name=data.get(
                        "forwarded_from"
                    )
                )
            )

        # -------------------------
        # Media
        # -------------------------

        file_name = data.get(
            "file"
        )

        if file_name:

            attachment = (
                TelegramAttachment(
                    type=TelegramMediaType.DOCUMENT,
                    file_path=file_name,
                )
            )

            message.attachments.append(
                attachment
            )

            message.message_type = (
                TelegramMessageType.DOCUMENT
            )

        else:

            message.message_type = (
                TelegramMessageType.TEXT
            )

        # -------------------------
        # Metadata
        # -------------------------

        message.metadata = dict(
            data
        )

        return message