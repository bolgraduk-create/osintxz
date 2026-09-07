"""
Telegram timeline mapper service.

Responsible for:

- converting Telegram collected items
  into timeline event payloads
- normalizing Telegram timestamps
- building stable source references

Does NOT:

- access database
- create timeline models
- manage transactions
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.collectors.base.models import (
    CollectedItem,
)

from app.models.timeline_event import (
    TimelineEventType,
)


class TelegramTimelineMapperService:
    """
    Maps Telegram collected items
    into timeline event payloads.
    """

    # ==========================================================
    # Public API
    # ==========================================================

    def map_items(
        self,
        items: list[CollectedItem],
    ) -> list[dict[str, Any]]:
        """
        Convert Telegram messages
        into timeline event payloads.
        """

        payloads: list[
            dict[str, Any]
        ] = []

        for item in items:

            payload = self.map_item(
                item
            )

            if payload is None:
                continue

            payloads.append(
                payload
            )

        return payloads

    def map_item(
        self,
        item: CollectedItem,
    ) -> dict[str, Any] | None:
        """
        Convert one collected item
        into a timeline payload.
        """

        event_time = (
            self._normalize_timestamp(
                item.timestamp
            )
        )

        if event_time is None:
            return None

        metadata = (
            item.metadata
            if isinstance(
                item.metadata,
                dict,
            )
            else {}
        )

        external_id = (
            self._normalize_value(
                item.external_id
            )
        )

        chat_id = (
            self._normalize_value(
                metadata.get(
                    "chat_id"
                )
            )
        )

        sender_id = (
            self._normalize_value(
                metadata.get(
                    "sender_id"
                )
            )
        )

        author = (
            self._normalize_value(
                item.author
            )
        )

        source_reference = (
            self._build_source_reference(
                chat_id=chat_id,
                external_id=external_id,
            )
        )

        title = (
            self._build_title(
                author=author,
                content=item.content,
            )
        )

        return {
            "event_type": (
                TimelineEventType.MESSAGE
            ),
            "title": title,
            "event_time": event_time,
            "source_reference": (
                source_reference
            ),
            "author": author,
            "sender_id": sender_id,
            "external_id": external_id,
            "chat_id": chat_id,
            "metadata": {
                "platform": "telegram",
                "item_type": (
                    self._normalize_value(
                        item.item_type
                    )
                ),
                "author": author,
                "sender_id": sender_id,
                "external_id": (
                    external_id
                ),
                "chat_id": chat_id,
                "reply_to": (
                    self._normalize_value(
                        metadata.get(
                            "reply_to"
                        )
                    )
                ),
            },
        }

    # ==========================================================
    # Timestamp
    # ==========================================================

    def _normalize_timestamp(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert timestamp to an
        ISO-compatible sortable string.
        """

        if value is None:
            return None

        if isinstance(
            value,
            datetime,
        ):

            return value.isoformat()

        text = str(
            value
        ).strip()

        if not text:
            return None

        try:

            parsed = (
                datetime.fromisoformat(
                    text.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            return parsed.isoformat()

        except ValueError:

            return text

    # ==========================================================
    # Reference
    # ==========================================================

    def _build_source_reference(
        self,
        chat_id: str | None,
        external_id: str | None,
    ) -> str | None:
        """
        Build stable Telegram
        timeline source reference.
        """

        if external_id is None:
            return None

        if chat_id is not None:

            return (
                f"telegram:"
                f"{chat_id}:"
                f"{external_id}"
            )

        return (
            f"telegram:"
            f"{external_id}"
        )

    # ==========================================================
    # Title
    # ==========================================================

    def _build_title(
        self,
        author: str | None,
        content: Any,
    ) -> str:
        """
        Build readable event title.
        """

        sender = (
            author
            or "Unknown Telegram user"
        )

        content_text = (
            str(
                content
            ).strip()
            if content is not None
            else ""
        )

        if not content_text:

            return (
                f"Telegram message from "
                f"{sender}"
            )

        compact_content = (
            " ".join(
                content_text.split()
            )
        )

        if len(
            compact_content
        ) > 80:

            compact_content = (
                compact_content[:77]
                + "..."
            )

        return (
            f"{sender}: "
            f"{compact_content}"
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _normalize_value(
        self,
        value: Any,
    ) -> str | None:
        """
        Normalize optional scalar value.
        """

        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        return text