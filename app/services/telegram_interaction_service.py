"""
Telegram interaction service.

Builds interaction statistics between Telegram participants.

Pipeline:

CollectedItem objects
        ↓
Reply resolution
        ↓
RelationshipAnalyzer
        ↓
Relationship candidates

Responsibilities:

- resolve Telegram reply references
- convert Telegram messages into analyzer format
- calculate participant interaction frequency
- calculate relationship strength and confidence
- preserve Telegram participant identifiers

Does NOT:

- create entities
- save relationships
- perform AI analysis
"""

from __future__ import annotations

from typing import Any

from app.analysis.analyzers.relationship_analyzer import (
    RelationshipAnalyzer,
)

from app.collectors.base.models import (
    CollectedItem,
    CollectedItemType,
)


class TelegramInteractionService:
    """
    Analyzes Telegram reply interactions.

    A directed relationship is detected when one participant
    replies to a message written by another participant.

    Direction:

    reply author
        ↓
    original message author
    """

    def __init__(
        self,
        analyzer: RelationshipAnalyzer | None = None,
    ) -> None:

        self.analyzer = (
            analyzer
            or RelationshipAnalyzer()
        )

    # ==========================================================
    # Main API
    # ==========================================================

    def analyze(
        self,
        items: list[CollectedItem],
    ) -> list[dict[str, Any]]:
        """
        Analyze Telegram items and return relationship candidates.
        """

        analyzer_messages, participants = (
            self._prepare_analyzer_messages(
                items
            )
        )

        if not analyzer_messages:
            return []

        analyzed_relationships = (
            self.analyzer.analyze(
                analyzer_messages
            )
        )

        result: list[
            dict[str, Any]
        ] = []

        for relationship in analyzed_relationships:

            source_key = relationship.get(
                "source"
            )

            target_key = relationship.get(
                "target"
            )

            if (
                not source_key
                or not target_key
            ):
                continue

            source_participant = (
                participants.get(
                    source_key
                )
            )

            target_participant = (
                participants.get(
                    target_key
                )
            )

            if (
                source_participant is None
                or target_participant is None
            ):
                continue

            source_value = (
                source_participant.get(
                    "value"
                )
            )

            target_value = (
                target_participant.get(
                    "value"
                )
            )

            if (
                not source_value
                or not target_value
            ):
                continue

            result.append(
                {
                    "source_key": source_key,
                    "target_key": target_key,
                    "source_value": source_value,
                    "target_value": target_value,
                    "source_sender_id": (
                        source_participant.get(
                            "sender_id"
                        )
                    ),
                    "target_sender_id": (
                        target_participant.get(
                            "sender_id"
                        )
                    ),
                    "relationship_type": (
                        "messaged"
                    ),
                    "frequency": int(
                        relationship.get(
                            "frequency",
                            0,
                        )
                    ),
                    "strength": float(
                        relationship.get(
                            "strength",
                            0.0,
                        )
                    ),
                    "confidence": float(
                        relationship.get(
                            "confidence",
                            0.6,
                        )
                    ),
                    "dates": list(
                        relationship.get(
                            "dates",
                            []
                        )
                    ),
                    "metadata": {
                        "source": "telegram",
                        "detection_method": (
                            "reply_reference"
                        ),
                    },
                }
            )

        return result

    # ==========================================================
    # Compatibility API
    # ==========================================================

    def interaction_matrix(
        self,
        items: list[CollectedItem],
    ) -> dict[tuple[str, str], int]:
        """
        Return participant interaction frequency matrix.
        """

        relationships = self.analyze(
            items
        )

        matrix: dict[
            tuple[str, str],
            int,
        ] = {}

        for relationship in relationships:

            source_value = relationship[
                "source_value"
            ]

            target_value = relationship[
                "target_value"
            ]

            matrix[
                (
                    source_value,
                    target_value,
                )
            ] = int(
                relationship.get(
                    "frequency",
                    0,
                )
            )

        return matrix

    def strongest_connections(
        self,
        items: list[CollectedItem],
        limit: int = 20,
    ) -> list[
        tuple[
            tuple[str, str],
            int,
        ]
    ]:
        """
        Return strongest Telegram reply connections.
        """

        matrix = self.interaction_matrix(
            items
        )

        return sorted(
            matrix.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

    # ==========================================================
    # Analyzer preparation
    # ==========================================================

    def _prepare_analyzer_messages(
        self,
        items: list[CollectedItem],
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        """
        Convert Telegram CollectedItem objects into
        RelationshipAnalyzer-compatible messages.
        """

        message_index = (
            self._build_message_index(
                items
            )
        )

        participants: dict[
            str,
            dict[str, Any],
        ] = {}

        analyzer_messages: list[
            dict[str, Any]
        ] = []

        for item in items:

            if not self._is_message(
                item
            ):
                continue

            reply_to = self._get_reply_to(
                item
            )

            if reply_to is None:
                continue

            chat_id = self._get_chat_id(
                item
            )

            if chat_id is None:
                continue

            replied_message = (
                message_index.get(
                    (
                        str(chat_id),
                        str(reply_to),
                    )
                )
            )

            if replied_message is None:
                continue

            source_participant = (
                self._extract_participant(
                    item
                )
            )

            target_participant = (
                self._extract_participant(
                    replied_message
                )
            )

            if (
                source_participant is None
                or target_participant is None
            ):
                continue

            source_key = (
                source_participant[
                    "key"
                ]
            )

            target_key = (
                target_participant[
                    "key"
                ]
            )

            # A reply to the participant's own message
            # does not create an entity relationship.
            if source_key == target_key:
                continue

            participants[
                source_key
            ] = source_participant

            participants[
                target_key
            ] = target_participant

            analyzer_messages.append(
                {
                    "sender": source_key,
                    "receiver": target_key,
                    "date": item.timestamp,
                }
            )

        return (
            analyzer_messages,
            participants,
        )

    def _build_message_index(
        self,
        items: list[CollectedItem],
    ) -> dict[
        tuple[str, str],
        CollectedItem,
    ]:
        """
        Index Telegram messages by chat ID and message ID.
        """

        index: dict[
            tuple[str, str],
            CollectedItem,
        ] = {}

        for item in items:

            if not self._is_message(
                item
            ):
                continue

            chat_id = self._get_chat_id(
                item
            )

            message_id = item.external_id

            if (
                chat_id is None
                or message_id is None
            ):
                continue

            index[
                (
                    str(chat_id),
                    str(message_id),
                )
            ] = item

        return index

    # ==========================================================
    # Participant extraction
    # ==========================================================

    def _extract_participant(
        self,
        item: CollectedItem,
    ) -> dict[str, Any] | None:
        """
        Extract Telegram participant identity.
        """

        participant_name = (
            self._clean_string(
                item.author
            )
        )

        sender_id = self._get_sender_id(
            item
        )

        if (
            participant_name is None
            and sender_id is None
        ):
            return None

        if participant_name is None:

            participant_name = (
                f"Telegram user {sender_id}"
            )

        normalized_value = (
            self._normalize_value(
                participant_name
            )
        )

        if sender_id is not None:

            participant_key = (
                f"telegram_id:{sender_id}"
            )

        else:

            participant_key = (
                f"telegram_name:{normalized_value}"
            )

        return {
            "key": participant_key,
            "value": participant_name,
            "normalized_value": (
                normalized_value
            ),
            "sender_id": sender_id,
        }

    # ==========================================================
    # Collected item helpers
    # ==========================================================

    def _is_message(
        self,
        item: CollectedItem,
    ) -> bool:
        """
        Check whether the collected item is a message.
        """

        return (
            item.item_type
            == CollectedItemType.MESSAGE
        )

    def _get_chat_id(
        self,
        item: CollectedItem,
    ) -> Any:
        """
        Return Telegram chat identifier.
        """

        return item.metadata.get(
            "chat_id"
        )

    def _get_sender_id(
        self,
        item: CollectedItem,
    ) -> Any:
        """
        Return Telegram sender identifier.
        """

        return item.metadata.get(
            "sender_id"
        )

    def _get_reply_to(
        self,
        item: CollectedItem,
    ) -> Any:
        """
        Return replied Telegram message identifier.
        """

        return item.metadata.get(
            "reply_to"
        )

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_value(
        self,
        value: str,
    ) -> str:
        """
        Normalize participant value.
        """

        return " ".join(
            str(
                value
            )
            .strip()
            .lower()
            .split()
        )

    def _clean_string(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert a value into a non-empty string.
        """

        if value is None:
            return None

        cleaned = str(
            value
        ).strip()

        if not cleaned:
            return None

        return cleaned