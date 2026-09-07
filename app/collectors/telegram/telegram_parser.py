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
    TelegramContact,
    TelegramExport,
    TelegramForwardInfo,
    TelegramLocation,
    TelegramMediaType,
    TelegramMessage,
    TelegramMessageType,
    TelegramPoll,
    TelegramPollOption,
    TelegramReplyInfo,
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

        path = Path(path)

        if path.is_dir():
            json_file = path / "result.json"
        else:
            json_file = path

        with json_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        export = TelegramExport(
            source=str(json_file),
        )

        export.version = str(
            data.get(
                "about",
                "",
            )
        )

        chats_data = (
            data.get("chats", {})
            .get("list", [])
        )

        if chats_data:

            for raw_chat in chats_data:

                export.chats.append(
                    self._parse_chat(
                        raw_chat,
                    )
                )

        else:

            export.chats.append(
                self._parse_chat(data)
            )

        return export

    # ==========================================================
    # Chat
    # ==========================================================

    def _parse_chat(
        self,
        data: dict[str, Any],
    ) -> TelegramChat:

        chat = TelegramChat()

        chat.id = str(
            data.get(
                "id",
                "",
            )
        )

        chat.title = (
            data.get("name")
            or data.get("title")
            or ""
        )

        chat.username = data.get(
            "username",
        )

        chat.description = data.get(
            "description",
        )

        chat.members_count = data.get(
            "members_count",
        )

        chat_type = str(
            data.get(
                "type",
                "",
            )
        ).lower()

        if chat_type == "private":

            chat.chat_type = TelegramChatType.PRIVATE

        elif chat_type == "group":

            chat.chat_type = TelegramChatType.GROUP

        elif chat_type == "supergroup":

            chat.chat_type = TelegramChatType.SUPERGROUP

        elif chat_type == "channel":

            chat.chat_type = TelegramChatType.CHANNEL

        else:

            chat.chat_type = TelegramChatType.UNKNOWN

        for raw_message in data.get(
            "messages",
            [],
        ):

            chat.messages.append(
                self._parse_message(
                    raw_message,
                    chat,
                )
            )

        return chat

    # ==========================================================
    # Message
    # ==========================================================

    def _parse_message(
        self,
        data: dict[str, Any],
        chat: TelegramChat,
    ) -> TelegramMessage:

        message = TelegramMessage(

            id=int(
                data.get(
                    "id",
                    0,
                )
            )

        )

        message.chat_id = chat.id
        message.chat_title = chat.title

        # ------------------------------------------------------
        # Sender
        # ------------------------------------------------------

        message.sender_name = data.get(
            "from",
        )

        message.sender_id = data.get(
            "from_id",
        )

        message.author = message.sender_name

        if (
            message.sender_name
            or message.sender_id
        ):

            message.sender = TelegramUser(

                id=message.sender_id,

                display_name=message.sender_name,

                first_name=message.sender_name,

            )

        # ------------------------------------------------------
        # Date
        # ------------------------------------------------------

        date = data.get(
            "date",
        )

        if date:

            try:

                message.timestamp = datetime.fromisoformat(
                    date.replace(
                        "T",
                        " ",
                    )
                )

            except Exception:

                try:

                    message.timestamp = datetime.strptime(
                        date,
                        "%Y-%m-%d %H:%M:%S %Z",
                    )

                except Exception:

                    message.timestamp = None

        edit_date = data.get(
            "edited",
        )

        if edit_date:

            message.edited = True

            try:

                message.edit_timestamp = datetime.fromisoformat(
                    edit_date.replace(
                        "T",
                        " ",
                    )
                )

            except Exception:
                pass

        # ------------------------------------------------------
        # Text
        # ------------------------------------------------------

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
                    parts.append(item)

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
        message.raw_text = message.text
        message.normalized_text = message.text.strip()

                # ------------------------------------------------------
        # Reply
        # ------------------------------------------------------

        reply_id = data.get(
            "reply_to_message_id",
        )

        if reply_id is not None:

            message.reply = TelegramReplyInfo(
                message_id=reply_id,
            )

        # ------------------------------------------------------
        # Forward
        # ------------------------------------------------------

        forwarded = data.get(
            "forwarded_from",
        )

        if forwarded:

            message.forward = TelegramForwardInfo(
                from_name=str(
                    forwarded,
                )
            )

        # ------------------------------------------------------
        # Statistics
        # ------------------------------------------------------

        message.views = data.get(
            "views",
        )

        message.forwards = data.get(
            "forwards",
        )

        message.replies_count = data.get(
            "replies",
        )

        # ------------------------------------------------------
        # Attachments
        # ------------------------------------------------------

        file_name = data.get(
            "file",
        )

        if file_name:

            media_type = TelegramMediaType.DOCUMENT
            message_type = TelegramMessageType.DOCUMENT
            mime = None

            lower = str(file_name).lower()

            raw_media_type = str(
                data.get(
                    "media_type",
                    "",
                )
            ).strip().lower()

            normalized_media_type = (
                raw_media_type
                .replace("-", "_")
                .replace(" ", "_")
            )

            is_voice_message = (
                normalized_media_type
                in {
                    "voice",
                    "voice_message",
                    "voice_note",
                }
            )

            if lower.endswith(
                (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                )
            ):

                media_type = TelegramMediaType.PHOTO
                message_type = TelegramMessageType.PHOTO
                mime = "image"

            elif lower.endswith(
                (
                    ".mp4",
                    ".mov",
                    ".avi",
                    ".mkv",
                )
            ):

                media_type = TelegramMediaType.VIDEO
                message_type = TelegramMessageType.VIDEO
                mime = "video"

            elif lower.endswith(
                (
                    ".ogg",
                    ".oga",
                    ".opus",
                    ".wav",
                    ".mp3",
                    ".m4a",
                )
            ):

                if is_voice_message:

                    media_type = (
                        TelegramMediaType.VOICE
                    )

                else:

                    media_type = (
                        TelegramMediaType.AUDIO
                    )

                # VOICE is the Telegram semantic origin.
                # AUDIO remains the processing modality.
                message_type = TelegramMessageType.AUDIO
                mime = "audio"

            attachment = TelegramAttachment(

                type=media_type,

                file_path=file_name,

                file_name=Path(file_name).name,

                mime_type=mime,

                size=data.get(
                    "file_size",
                ),

                duration=(
                    data.get(
                        "duration_seconds"
                    )
                    or
                    data.get(
                        "duration"
                    )
                ),

                metadata={
                    "telegram_media_type_raw": (
                        raw_media_type
                        or None
                    ),
                    "is_voice_message": is_voice_message,
                },

            )

            message.attachments.append(
                attachment,
            )

            message.message_type = (
                message_type
            )

        else:

            message.message_type = (
                TelegramMessageType.TEXT
            )

        # ------------------------------------------------------
        # Contact
        # ------------------------------------------------------

        if "contact_information" in data:

            contact = data.get(
                "contact_information",
                {},
            )

            if isinstance(
                contact,
                dict,
            ):

                message.contact = TelegramContact(

                    first_name=contact.get(
                        "first_name",
                    ),

                    last_name=contact.get(
                        "last_name",
                    ),

                    phone_number=contact.get(
                        "phone_number",
                    ),

                    user_id=contact.get(
                        "user_id",
                    ),

                )

        # ------------------------------------------------------
        # Location
        # ------------------------------------------------------

        if (
            "latitude" in data
            and "longitude" in data
        ):

            message.location = TelegramLocation(

                latitude=float(
                    data["latitude"]
                ),

                longitude=float(
                    data["longitude"]
                ),

                title=data.get(
                    "title",
                ),

                address=data.get(
                    "address",
                ),

            )

                    # ------------------------------------------------------
        # Poll
        # ------------------------------------------------------

        poll = data.get(
            "poll",
        )

        if isinstance(
            poll,
            dict,
        ):

            telegram_poll = TelegramPoll(

                question=poll.get(
                    "question",
                    "",
                ),

                multiple_answers=poll.get(
                    "multiple_answers",
                    False,
                ),

                anonymous=poll.get(
                    "anonymous",
                    True,
                ),

            )

            for option in poll.get(
                "options",
                [],
            ):

                if isinstance(
                    option,
                    dict,
                ):

                    telegram_poll.options.append(

                        TelegramPollOption(

                            text=option.get(
                                "text",
                                "",
                            ),

                            votes=option.get(
                                "voter_count",
                                0,
                            ),

                        )

                    )

            message.poll = telegram_poll

        # ------------------------------------------------------
        # Flags
        # ------------------------------------------------------

        message.outgoing = (
            data.get(
                "from",
            )
            is not None
        )

        message.incoming = (
            not message.outgoing
        )

        message.pinned = bool(
            data.get(
                "pinned",
                False,
            )
        )

        message.silent = bool(
            data.get(
                "silent",
                False,
            )
        )

        message.scheduled = bool(
            data.get(
                "scheduled",
                False,
            )
        )

        # ------------------------------------------------------
        # Metadata
        # ------------------------------------------------------

        message.metadata = dict(data)

        return message