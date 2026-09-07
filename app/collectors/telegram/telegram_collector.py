"""
Telegram collector.

Converts Telegram export into
CollectedItem objects.

Responsibilities:

- use TelegramParser
- convert messages
- expose Telegram voice attachments as audio items
- preserve Telegram voice-message semantics
- resolve attachment paths relative to export root
- return collected items

Important:

Telegram VOICE
    = semantic origin of the attachment

CollectedItemType.AUDIO
    = processing modality

VOICE != generic audio.

A Telegram voice message therefore remains identifiable
as a voice message while still entering the existing audio
processing pipeline.

Does NOT:

- save to database
- create Evidence
- perform transcription
- perform AI analysis
"""

from __future__ import annotations

import mimetypes

from pathlib import (
    Path,
)

from app.collectors.base.models import (
    CollectedItem,
    CollectedItemType,
)

from .telegram_models import (
    TelegramMediaType,
)

from .telegram_parser import (
    TelegramParser,
)


class TelegramCollector:
    """
    Telegram collection adapter.
    """

    def __init__(
        self,
    ) -> None:

        self.parser = (
            TelegramParser()
        )

    # ======================================================
    # Collection
    # ======================================================

    def collect(
        self,
        path: str | Path,
    ) -> list[CollectedItem]:
        """
        Collect Telegram messages and supported
        attachment objects.
        """

        source_path = Path(
            path
        )

        export_root = (
            source_path
            if source_path.is_dir()
            else source_path.parent
        )

        export = (
            self.parser.parse(
                source_path
            )
        )

        items: list[
            CollectedItem
        ] = []

        for chat in export.chats:

            for message in chat.messages:

                # ==============================================
                # Message itself
                # ==============================================

                items.append(
                    self._convert_message(
                        message,
                        chat,
                    )
                )

                # ==============================================
                # Voice attachments
                # ==============================================

                attachments = getattr(
                    message,
                    "attachments",
                    [],
                )

                for (
                    attachment_index,
                    attachment,
                ) in enumerate(
                    attachments
                ):

                    if (
                        getattr(
                            attachment,
                            "type",
                            None,
                        )
                        !=
                        TelegramMediaType.VOICE
                    ):

                        continue

                    items.append(
                        self._convert_voice_attachment(
                            message=message,
                            chat=chat,
                            attachment=attachment,
                            attachment_index=(
                                attachment_index
                            ),
                            export_root=(
                                export_root
                            ),
                        )
                    )

        return items

    # ======================================================
    # Message
    # ======================================================

    def _convert_message(
        self,
        message,
        chat,
    ) -> CollectedItem:
        """
        Convert Telegram message into CollectedItem.
        """

        attachments = getattr(
            message,
            "attachments",
            [],
        )

        return CollectedItem(
            source="telegram",

            item_type=(
                CollectedItemType.MESSAGE
            ),

            content=message.text,

            timestamp=message.timestamp,

            title=chat.title,

            author=message.sender_name,

            external_id=str(
                message.id
            ),

            metadata={
                "chat_id": chat.id,

                "chat_title": (
                    chat.title
                ),

                "sender_id": (
                    message.sender_id
                ),

                "reply_to": (
                    message.reply.message_id
                    if message.reply
                    else None
                ),

                "message_type": (
                    message.message_type.value
                    if getattr(
                        message,
                        "message_type",
                        None,
                    )
                    else None
                ),

                "attachments": [
                    attachment.file_path
                    for attachment
                    in attachments
                ],

                "voice_attachment_count": sum(
                    1
                    for attachment
                    in attachments
                    if (
                        getattr(
                            attachment,
                            "type",
                            None,
                        )
                        ==
                        TelegramMediaType.VOICE
                    )
                ),
            },
        )

    # ======================================================
    # Voice attachment
    # ======================================================

    def _convert_voice_attachment(
        self,
        *,
        message,
        chat,
        attachment,
        attachment_index: int,
        export_root: Path,
    ) -> CollectedItem:
        """
        Convert Telegram VOICE attachment to the
        generic AUDIO processing modality.

        Telegram semantic information remains preserved
        inside metadata.
        """

        resolved_path = (
            self._resolve_attachment_path(
                attachment.file_path,
                export_root=(
                    export_root
                ),
            )
        )

        mime_type = (
            self._resolve_audio_mime_type(
                file_path=resolved_path,
                file_name=(
                    attachment.file_name
                ),
                fallback=(
                    attachment.mime_type
                ),
            )
        )

        message_id = str(
            message.id
        )

        external_id = (
            f"{message_id}:voice:"
            f"{attachment_index}"
        )

        title = (
            attachment.file_name
            or
            f"Voice message {message_id}"
        )

        content = (
            attachment.caption
            or
            message.text
            or
            ""
        )

        attachment_metadata = getattr(
            attachment,
            "metadata",
            {},
        )

        if not isinstance(
            attachment_metadata,
            dict,
        ):

            attachment_metadata = {}

        return CollectedItem(
            source="telegram",

            # --------------------------------------------------
            # Processing modality
            # --------------------------------------------------

            item_type=(
                CollectedItemType.AUDIO
            ),

            content=content,

            timestamp=message.timestamp,

            title=title,

            author=message.sender_name,

            external_id=external_id,

            metadata={
                # ----------------------------------------------
                # Telegram semantic origin
                # ----------------------------------------------

                "telegram_media_type": (
                    TelegramMediaType
                    .VOICE
                    .value
                ),

                "telegram_media_type_raw": (
                    attachment_metadata.get(
                        "telegram_media_type_raw"
                    )
                ),

                "is_voice_message": True,

                "processing_modality": (
                    "audio"
                ),

                # ----------------------------------------------
                # Parent Telegram message
                # ----------------------------------------------

                "telegram_message_id": (
                    message_id
                ),

                "attachment_index": (
                    attachment_index
                ),

                "chat_id": chat.id,

                "chat_title": chat.title,

                "sender_id": (
                    message.sender_id
                ),

                # ----------------------------------------------
                # File
                # ----------------------------------------------

                "file_path": (
                    str(
                        resolved_path
                    )
                    if resolved_path
                    is not None
                    else attachment.file_path
                ),

                "original_file_path": (
                    attachment.file_path
                ),

                "file_name": (
                    attachment.file_name
                ),

                "mime_type": (
                    mime_type
                ),

                "size": (
                    attachment.size
                ),

                "duration": (
                    attachment.duration
                ),
            },
        )

    # ======================================================
    # Path resolution
    # ======================================================

    @staticmethod
    def _resolve_attachment_path(
        file_path: str | None,
        *,
        export_root: Path,
    ) -> Path | None:
        """
        Resolve Telegram export-relative attachment path.

        Telegram Desktop exports normally store media paths
        relative to result.json.
        """

        if not file_path:

            return None

        candidate = Path(
            file_path
        )

        if not candidate.is_absolute():

            candidate = (
                export_root
                /
                candidate
            )

        return candidate.resolve(
            strict=False
        )

    # ======================================================
    # MIME
    # ======================================================

    @staticmethod
    def _resolve_audio_mime_type(
        *,
        file_path: Path | None,
        file_name: str | None,
        fallback: str | None,
    ) -> str:
        """
        Resolve a more useful audio MIME type than the
        generic Telegram parser value `audio`.
        """

        candidate_name = None

        if file_path is not None:

            candidate_name = (
                file_path.name
            )

        elif file_name:

            candidate_name = (
                file_name
            )

        if candidate_name:

            guessed, _ = (
                mimetypes.guess_type(
                    candidate_name
                )
            )

            if guessed:

                return guessed

        if (
            fallback
            and
            str(
                fallback
            ).startswith(
                "audio/"
            )
        ):

            return str(
                fallback
            )

        return "audio/ogg"