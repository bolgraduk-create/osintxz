"""
Investigation summary builder.

Builds a deterministic investigation summary
from data already stored inside a Case.

Responsibilities:

- collect investigation data through services
- calculate investigation statistics
- build a human-readable Markdown summary
- prepare structured report metadata

Does NOT:

- access repositories directly
- commit database transactions
- create Report records
- execute AI analysis
- modify investigation data
"""

from __future__ import annotations

import json

from collections import Counter
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.entity_service import EntityService
from app.services.message_service import MessageService
from app.services.relationship_service import RelationshipService
from app.services.timeline_service import TimelineService


class InvestigationSummaryBuilder:
    """
    Builds a deterministic summary for a Case.

    The builder receives application services
    and never accesses repositories directly.
    """

    def __init__(
        self,
        message_service: MessageService,
        entity_service: EntityService,
        relationship_service: RelationshipService,
        timeline_service: TimelineService,
    ) -> None:
        self.message_service = message_service
        self.entity_service = entity_service
        self.relationship_service = relationship_service
        self.timeline_service = timeline_service

    # ==========================================================
    # Public API
    # ==========================================================

    def build(
        self,
        case_id: UUID,
    ) -> dict[str, Any]:
        """
        Build investigation summary.

        Returns:

        {
            "title": str,
            "content": str,
            "metadata": dict,
            "metadata_json": str,
        }
        """

        messages = self.message_service.get_case_messages(
            case_id
        )

        entities = self.entity_service.get_case_entities(
            case_id
        )

        relationships = (
            self.relationship_service.get_case_relationships(
                case_id
            )
        )

        timeline_events = (
            self.timeline_service.get_case_timeline(
                case_id
            )
        )

        message_statistics = (
            self._build_message_statistics(
                messages
            )
        )

        entity_statistics = (
            self._build_entity_statistics(
                entities
            )
        )

        relationship_statistics = (
            self._build_relationship_statistics(
                relationships
            )
        )

        timeline_statistics = (
            self._build_timeline_statistics(
                timeline_events
            )
        )

        metadata: dict[str, Any] = {
            "case_id": str(case_id),
            "generated_at": datetime.now().astimezone().isoformat(),
            "messages": message_statistics,
            "entities": entity_statistics,
            "relationships": relationship_statistics,
            "timeline": timeline_statistics,
        }

        content = self._build_markdown(
            case_id=case_id,
            message_statistics=message_statistics,
            entity_statistics=entity_statistics,
            relationship_statistics=relationship_statistics,
            timeline_statistics=timeline_statistics,
        )

        return {
            "title": "Investigation Summary",
            "content": content,
            "metadata": metadata,
            "metadata_json": json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2,
            ),
        }

    # ==========================================================
    # Message statistics
    # ==========================================================

    def _build_message_statistics(
        self,
        messages: list[Any],
    ) -> dict[str, Any]:
        """
        Calculate message statistics.
        """

        sender_counter: Counter[str] = Counter()
        chat_counter: Counter[str] = Counter()

        dated_messages: list[datetime] = []

        messages_with_text = 0
        messages_without_text = 0
        reply_messages = 0
        messages_with_external_id = 0

        for message in messages:
            sender = self._clean_text(
                getattr(
                    message,
                    "sender",
                    None,
                )
            )

            if sender is not None:
                sender_counter[sender] += 1

            chat_name = self._clean_text(
                getattr(
                    message,
                    "chat_name",
                    None,
                )
            )

            if chat_name is not None:
                chat_counter[chat_name] += 1

            text = self._clean_text(
                getattr(
                    message,
                    "text",
                    None,
                )
            )

            if text is None:
                messages_without_text += 1
            else:
                messages_with_text += 1

            sent_at = getattr(
                message,
                "sent_at",
                None,
            )

            if isinstance(
                sent_at,
                datetime,
            ):
                dated_messages.append(
                    sent_at
                )

            if getattr(
                message,
                "reply_to_id",
                None,
            ) is not None:
                reply_messages += 1

            if self._clean_text(
                getattr(
                    message,
                    "external_id",
                    None,
                )
            ) is not None:
                messages_with_external_id += 1

        first_message_at = self._minimum_datetime(
            dated_messages
        )

        last_message_at = self._maximum_datetime(
            dated_messages
        )

        return {
            "total": len(messages),
            "with_text": messages_with_text,
            "without_text": messages_without_text,
            "with_date": len(dated_messages),
            "without_date": (
                len(messages)
                - len(dated_messages)
            ),
            "replies": reply_messages,
            "with_external_id": messages_with_external_id,
            "unique_senders": len(sender_counter),
            "unique_chats": len(chat_counter),
            "first_message_at": self._datetime_to_string(
                first_message_at
            ),
            "last_message_at": self._datetime_to_string(
                last_message_at
            ),
            "top_senders": self._counter_to_list(
                sender_counter,
                limit=10,
            ),
            "top_chats": self._counter_to_list(
                chat_counter,
                limit=10,
            ),
        }

    # ==========================================================
    # Entity statistics
    # ==========================================================

    def _build_entity_statistics(
        self,
        entities: list[Any],
    ) -> dict[str, Any]:
        """
        Calculate entity statistics.
        """

        type_counter: Counter[str] = Counter()

        confidence_values: list[float] = []

        entities_with_metadata = 0
        entities_with_description = 0

        ranked_entities: list[
            dict[str, Any]
        ] = []

        for entity in entities:
            entity_type = self._enum_to_string(
                getattr(
                    entity,
                    "entity_type",
                    None,
                )
            )

            type_counter[entity_type] += 1

            confidence = self._to_float(
                getattr(
                    entity,
                    "confidence",
                    None,
                )
            )

            if confidence is not None:
                confidence_values.append(
                    confidence
                )

            if self._clean_text(
                getattr(
                    entity,
                    "metadata_json",
                    None,
                )
            ) is not None:
                entities_with_metadata += 1

            if self._clean_text(
                getattr(
                    entity,
                    "description",
                    None,
                )
            ) is not None:
                entities_with_description += 1

            value = self._clean_text(
                getattr(
                    entity,
                    "value",
                    None,
                )
            )

            if value is None:
                value = "Unknown entity"

            ranked_entities.append(
                {
                    "id": self._uuid_to_string(
                        getattr(
                            entity,
                            "id",
                            None,
                        )
                    ),
                    "value": value,
                    "type": entity_type,
                    "confidence": confidence,
                }
            )

        ranked_entities.sort(
            key=lambda item: (
                item["confidence"]
                if item["confidence"] is not None
                else -1.0
            ),
            reverse=True,
        )

        return {
            "total": len(entities),
            "by_type": self._counter_to_list(
                type_counter
            ),
            "average_confidence": (
                self._average(
                    confidence_values
                )
            ),
            "with_metadata": entities_with_metadata,
            "with_description": entities_with_description,
            "top_confidence_entities": (
                ranked_entities[:10]
            ),
        }

    # ==========================================================
    # Relationship statistics
    # ==========================================================

    def _build_relationship_statistics(
        self,
        relationships: list[Any],
    ) -> dict[str, Any]:
        """
        Calculate relationship statistics.
        """

        type_counter: Counter[str] = Counter()

        confidence_values: list[float] = []

        connected_entity_ids: set[str] = set()

        relationships_with_metadata = 0
        relationships_with_description = 0

        for relationship in relationships:
            relationship_type = (
                self._enum_to_string(
                    getattr(
                        relationship,
                        "relationship_type",
                        None,
                    )
                )
            )

            type_counter[relationship_type] += 1

            confidence = self._to_float(
                getattr(
                    relationship,
                    "confidence",
                    None,
                )
            )

            if confidence is not None:
                confidence_values.append(
                    confidence
                )

            source_entity_id = (
                self._uuid_to_string(
                    getattr(
                        relationship,
                        "source_entity_id",
                        None,
                    )
                )
            )

            target_entity_id = (
                self._uuid_to_string(
                    getattr(
                        relationship,
                        "target_entity_id",
                        None,
                    )
                )
            )

            if source_entity_id is not None:
                connected_entity_ids.add(
                    source_entity_id
                )

            if target_entity_id is not None:
                connected_entity_ids.add(
                    target_entity_id
                )

            if self._clean_text(
                getattr(
                    relationship,
                    "metadata_json",
                    None,
                )
            ) is not None:
                relationships_with_metadata += 1

            if self._clean_text(
                getattr(
                    relationship,
                    "description",
                    None,
                )
            ) is not None:
                relationships_with_description += 1

        return {
            "total": len(relationships),
            "by_type": self._counter_to_list(
                type_counter
            ),
            "average_confidence": (
                self._average(
                    confidence_values
                )
            ),
            "connected_entities": len(
                connected_entity_ids
            ),
            "with_metadata": (
                relationships_with_metadata
            ),
            "with_description": (
                relationships_with_description
            ),
        }

    # ==========================================================
    # Timeline statistics
    # ==========================================================

    def _build_timeline_statistics(
        self,
        timeline_events: list[Any],
    ) -> dict[str, Any]:
        """
        Calculate timeline statistics.
        """

        type_counter: Counter[str] = Counter()

        parsed_event_times: list[datetime] = []

        events_with_entity = 0
        events_with_source_reference = 0
        events_with_metadata = 0

        for event in timeline_events:
            event_type = self._enum_to_string(
                getattr(
                    event,
                    "event_type",
                    None,
                )
            )

            type_counter[event_type] += 1

            event_time = getattr(
                event,
                "event_time",
                None,
            )

            parsed_time = self._parse_datetime(
                event_time
            )

            if parsed_time is not None:
                parsed_event_times.append(
                    parsed_time
                )

            if getattr(
                event,
                "entity_id",
                None,
            ) is not None:
                events_with_entity += 1

            if self._clean_text(
                getattr(
                    event,
                    "source_reference",
                    None,
                )
            ) is not None:
                events_with_source_reference += 1

            if self._clean_text(
                getattr(
                    event,
                    "metadata_json",
                    None,
                )
            ) is not None:
                events_with_metadata += 1

        first_event_at = self._minimum_datetime(
            parsed_event_times
        )

        last_event_at = self._maximum_datetime(
            parsed_event_times
        )

        return {
            "total": len(timeline_events),
            "by_type": self._counter_to_list(
                type_counter
            ),
            "with_valid_time": len(
                parsed_event_times
            ),
            "without_valid_time": (
                len(timeline_events)
                - len(parsed_event_times)
            ),
            "with_entity": events_with_entity,
            "with_source_reference": (
                events_with_source_reference
            ),
            "with_metadata": events_with_metadata,
            "first_event_at": (
                self._datetime_to_string(
                    first_event_at
                )
            ),
            "last_event_at": (
                self._datetime_to_string(
                    last_event_at
                )
            ),
        }

    # ==========================================================
    # Markdown generation
    # ==========================================================

    def _build_markdown(
        self,
        case_id: UUID,
        message_statistics: dict[str, Any],
        entity_statistics: dict[str, Any],
        relationship_statistics: dict[str, Any],
        timeline_statistics: dict[str, Any],
    ) -> str:
        """
        Build the human-readable Markdown report.
        """

        generated_at = (
            datetime.now()
            .astimezone()
            .strftime(
                "%Y-%m-%d %H:%M:%S %Z"
            )
        )

        lines: list[str] = [
            "# Investigation Summary",
            "",
            f"**Case ID:** `{case_id}`",
            f"**Generated at:** {generated_at}",
            "",
            "## Overview",
            "",
            (
                f"- Messages: "
                f"{message_statistics['total']}"
            ),
            (
                f"- Entities: "
                f"{entity_statistics['total']}"
            ),
            (
                f"- Relationships: "
                f"{relationship_statistics['total']}"
            ),
            (
                f"- Timeline events: "
                f"{timeline_statistics['total']}"
            ),
            "",
        ]

        self._append_message_section(
            lines,
            message_statistics,
        )

        self._append_entity_section(
            lines,
            entity_statistics,
        )

        self._append_relationship_section(
            lines,
            relationship_statistics,
        )

        self._append_timeline_section(
            lines,
            timeline_statistics,
        )

        return "\n".join(lines).strip()

    def _append_message_section(
        self,
        lines: list[str],
        statistics: dict[str, Any],
    ) -> None:
        """
        Append message statistics.
        """

        lines.extend(
            [
                "## Messages",
                "",
                (
                    f"- Total messages: "
                    f"{statistics['total']}"
                ),
                (
                    f"- Messages with text: "
                    f"{statistics['with_text']}"
                ),
                (
                    f"- Messages without text: "
                    f"{statistics['without_text']}"
                ),
                (
                    f"- Reply messages: "
                    f"{statistics['replies']}"
                ),
                (
                    f"- Unique senders: "
                    f"{statistics['unique_senders']}"
                ),
                (
                    f"- Unique chats: "
                    f"{statistics['unique_chats']}"
                ),
                (
                    f"- First message: "
                    f"{self._display_value(statistics['first_message_at'])}"
                ),
                (
                    f"- Last message: "
                    f"{self._display_value(statistics['last_message_at'])}"
                ),
                "",
                "### Most active senders",
                "",
            ]
        )

        self._append_ranked_counts(
            lines,
            statistics["top_senders"],
            empty_text="No sender information available.",
        )

        lines.extend(
            [
                "",
                "### Most active chats",
                "",
            ]
        )

        self._append_ranked_counts(
            lines,
            statistics["top_chats"],
            empty_text="No chat information available.",
        )

        lines.append("")

    def _append_entity_section(
        self,
        lines: list[str],
        statistics: dict[str, Any],
    ) -> None:
        """
        Append entity statistics.
        """

        lines.extend(
            [
                "## Entities",
                "",
                (
                    f"- Total entities: "
                    f"{statistics['total']}"
                ),
                (
                    f"- Average confidence: "
                    f"{self._format_confidence(statistics['average_confidence'])}"
                ),
                (
                    f"- Entities with metadata: "
                    f"{statistics['with_metadata']}"
                ),
                (
                    f"- Entities with description: "
                    f"{statistics['with_description']}"
                ),
                "",
                "### Entity types",
                "",
            ]
        )

        self._append_ranked_counts(
            lines,
            statistics["by_type"],
            empty_text="No entities available.",
        )

        lines.extend(
            [
                "",
                "### Highest-confidence entities",
                "",
            ]
        )

        top_entities = statistics[
            "top_confidence_entities"
        ]

        if not top_entities:
            lines.append(
                "No entities available."
            )
        else:
            for index, entity in enumerate(
                top_entities,
                start=1,
            ):
                lines.append(
                    (
                        f"{index}. "
                        f"{entity['value']} "
                        f"({entity['type']}, "
                        f"confidence: "
                        f"{self._format_confidence(entity['confidence'])})"
                    )
                )

        lines.append("")

    def _append_relationship_section(
        self,
        lines: list[str],
        statistics: dict[str, Any],
    ) -> None:
        """
        Append relationship statistics.
        """

        lines.extend(
            [
                "## Relationships",
                "",
                (
                    f"- Total relationships: "
                    f"{statistics['total']}"
                ),
                (
                    f"- Connected entities: "
                    f"{statistics['connected_entities']}"
                ),
                (
                    f"- Average confidence: "
                    f"{self._format_confidence(statistics['average_confidence'])}"
                ),
                (
                    f"- Relationships with metadata: "
                    f"{statistics['with_metadata']}"
                ),
                "",
                "### Relationship types",
                "",
            ]
        )

        self._append_ranked_counts(
            lines,
            statistics["by_type"],
            empty_text="No relationships available.",
        )

        lines.append("")

    def _append_timeline_section(
        self,
        lines: list[str],
        statistics: dict[str, Any],
    ) -> None:
        """
        Append timeline statistics.
        """

        lines.extend(
            [
                "## Timeline",
                "",
                (
                    f"- Total events: "
                    f"{statistics['total']}"
                ),
                (
                    f"- Events linked to entities: "
                    f"{statistics['with_entity']}"
                ),
                (
                    f"- Events with source reference: "
                    f"{statistics['with_source_reference']}"
                ),
                (
                    f"- First event: "
                    f"{self._display_value(statistics['first_event_at'])}"
                ),
                (
                    f"- Last event: "
                    f"{self._display_value(statistics['last_event_at'])}"
                ),
                "",
                "### Timeline event types",
                "",
            ]
        )

        self._append_ranked_counts(
            lines,
            statistics["by_type"],
            empty_text="No timeline events available.",
        )

        lines.append("")

    # ==========================================================
    # Formatting helpers
    # ==========================================================

    def _append_ranked_counts(
        self,
        lines: list[str],
        items: list[dict[str, Any]],
        empty_text: str,
    ) -> None:
        """
        Append a numbered list of count values.
        """

        if not items:
            lines.append(
                empty_text
            )
            return

        for index, item in enumerate(
            items,
            start=1,
        ):
            lines.append(
                (
                    f"{index}. "
                    f"{item['value']}: "
                    f"{item['count']}"
                )
            )

    def _counter_to_list(
        self,
        counter: Counter[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert Counter to JSON-safe list.
        """

        items = counter.most_common(
            limit
        )

        return [
            {
                "value": value,
                "count": count,
            }
            for value, count in items
        ]

    def _enum_to_string(
        self,
        value: Any,
    ) -> str:
        """
        Convert Enum or arbitrary value to string.
        """

        if value is None:
            return "unknown"

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:
            return str(
                enum_value
            )

        return str(
            value
        )

    def _clean_text(
        self,
        value: Any,
    ) -> str | None:
        """
        Normalize optional text value.
        """

        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        return text

    def _to_float(
        self,
        value: Any,
    ) -> float | None:
        """
        Safely convert a value to float.
        """

        if value is None:
            return None

        try:
            return float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    def _average(
        self,
        values: list[float],
    ) -> float | None:
        """
        Calculate average value.
        """

        if not values:
            return None

        return round(
            sum(values) / len(values),
            4,
        )

    def _format_confidence(
        self,
        confidence: float | None,
    ) -> str:
        """
        Format confidence for Markdown.
        """

        if confidence is None:
            return "N/A"

        return f"{confidence:.2f}"

    def _uuid_to_string(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert UUID-like value to string.
        """

        if value is None:
            return None

        return str(
            value
        )

    def _parse_datetime(
        self,
        value: Any,
    ) -> datetime | None:
        """
        Parse datetime or ISO datetime string.
        """

        if isinstance(
            value,
            datetime,
        ):
            return value

        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        normalized_text = text.replace(
            "Z",
            "+00:00",
        )

        try:
            return datetime.fromisoformat(
                normalized_text
            )
        except ValueError:
            return None

    def _minimum_datetime(
        self,
        values: list[datetime],
    ) -> datetime | None:
        """
        Return the earliest datetime safely.
        """

        normalized_values = [
            self._normalize_datetime_for_comparison(
                value
            )
            for value in values
        ]

        if not normalized_values:
            return None

        return min(
            normalized_values
        )

    def _maximum_datetime(
        self,
        values: list[datetime],
    ) -> datetime | None:
        """
        Return the latest datetime safely.
        """

        normalized_values = [
            self._normalize_datetime_for_comparison(
                value
            )
            for value in values
        ]

        if not normalized_values:
            return None

        return max(
            normalized_values
        )

    def _normalize_datetime_for_comparison(
        self,
        value: datetime,
    ) -> datetime:
        """
        Make datetime comparison safe when some
        values are timezone-aware and others are naive.
        """

        if value.tzinfo is None:
            return value.replace(
                tzinfo=datetime.now()
                .astimezone()
                .tzinfo
            )

        return value

    def _datetime_to_string(
        self,
        value: datetime | None,
    ) -> str | None:
        """
        Convert datetime to ISO string.
        """

        if value is None:
            return None

        return value.isoformat()

    def _display_value(
        self,
        value: Any,
    ) -> str:
        """
        Format nullable value for Markdown.
        """

        if value is None:
            return "N/A"

        return str(
            value
        )