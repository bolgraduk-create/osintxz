"""
Telegram entity mapper service.

Converts Telegram collected items
into investigation entity payloads.

Responsibilities:

- map Telegram message authors
- prepare entity payloads
- normalize participant values
- prevent duplicate participant payloads
- use shared entity normalization contract

Does NOT:

- save entities
- create relationships
- perform AI analysis
- perform identity resolution
"""

from __future__ import annotations

from typing import Any

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.models.entity import (
    EntityType,
)


class TelegramEntityMapperService:
    """
    Maps Telegram collected items
    into investigation entities.
    """

    def __init__(
        self,
        normalizer: EntityNormalizer | None = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

    def participants_to_entities(
        self,
        items,
    ) -> list[dict[str, Any]]:
        """
        Convert Telegram message authors
        into person entity payloads.
        """

        participants: dict[
            str,
            dict[str, Any],
        ] = {}

        for item in items:

            author = self._get_author(
                item
            )

            sender_id = self._get_sender_id(
                item
            )

            if (
                not author
                and sender_id is None
            ):
                continue

            if not author:

                author = (
                    f"Telegram user {sender_id}"
                )

            normalized_value = (
                self.normalizer.normalize(
                    EntityType.PERSON,
                    author,
                )
            )

            if not normalized_value:
                continue

            participant_key = self._build_key(
                normalized_value=normalized_value,
                sender_id=sender_id,
            )

            if participant_key in participants:
                continue

            metadata = {
                "source": "telegram",
            }

            if sender_id is not None:

                metadata["telegram_id"] = str(
                    sender_id
                )

            participants[
                participant_key
            ] = {
                "entity_type": (
                    EntityType.PERSON
                ),
                "value": author,
                "normalized_value": (
                    normalized_value
                ),
                "confidence": 1.0,
                "metadata": metadata,
                "description": (
                    "Telegram participant"
                ),
            }

        return list(
            participants.values()
        )

    # ==========================================================
    # Collected item extraction
    # ==========================================================

    def _get_author(
        self,
        item,
    ) -> str | None:
        """
        Extract author from CollectedItem.
        """

        if isinstance(
            item,
            dict,
        ):

            author = item.get(
                "author"
            )

        else:

            author = getattr(
                item,
                "author",
                None,
            )

        if author is None:
            return None

        value = str(
            author
        ).strip()

        if not value:
            return None

        return value

    def _get_sender_id(
        self,
        item,
    ):
        """
        Extract Telegram sender ID
        from CollectedItem metadata.
        """

        if isinstance(
            item,
            dict,
        ):

            metadata = (
                item.get(
                    "metadata"
                )
                or {}
            )

        else:

            metadata = (
                getattr(
                    item,
                    "metadata",
                    None,
                )
                or {}
            )

        if not isinstance(
            metadata,
            dict,
        ):
            return None

        return metadata.get(
            "sender_id"
        )

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_value(
        self,
        value: str,
    ) -> str:
        """
        Backward-compatible participant
        normalization helper.

        Delegates to the shared
        EntityNormalizer contract.
        """

        return self.normalizer.normalize(
            EntityType.PERSON,
            value,
        )

    def _build_key(
        self,
        normalized_value: str,
        sender_id,
    ) -> str:
        """
        Build a stable mapper-level
        deduplication key.

        Telegram sender ID has priority
        inside one collected batch.
        """

        if sender_id is not None:

            return (
                f"id:{sender_id}"
            )

        return (
            f"name:{normalized_value}"
        )