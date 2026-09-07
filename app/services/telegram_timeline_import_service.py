"""
Telegram timeline import service.

Responsible for:

- mapping Telegram items to timeline events
- resolving event authors to entities
- preventing duplicate timeline events
- creating timeline records

Does NOT:

- parse Telegram exports
- manage application transactions
- access repositories directly
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.collectors.base.models import (
    CollectedItem,
)

from app.models.entity import (
    Entity,
    EntityType,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.telegram_timeline_mapper_service import (
    TelegramTimelineMapperService,
)

from app.services.timeline_service import (
    TimelineService,
)


class TelegramTimelineImportService:
    """
    Imports Telegram events
    into investigation timeline.
    """

    def __init__(
        self,
        mapper: TelegramTimelineMapperService,
        timeline_service: TimelineService,
        entity_service: EntityService,
    ) -> None:

        self.mapper = mapper

        self.timeline_service = (
            timeline_service
        )

        self.entity_service = (
            entity_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def import_events(
        self,
        case_id: UUID,
        items: list[CollectedItem],
    ) -> dict[str, int]:
        """
        Create Telegram timeline events.
        """

        payloads = (
            self.mapper.map_items(
                items
            )
        )

        existing_events = (
            self.timeline_service
            .get_case_timeline(
                case_id
            )
        )

        existing_references = {
            event.source_reference
            for event in existing_events
            if event.source_reference
        }

        entities = (
            self.entity_service
            .get_case_entities(
                case_id
            )
        )

        entity_by_sender_id = (
            self._build_sender_id_index(
                entities
            )
        )

        entity_by_name = (
            self._build_name_index(
                entities
            )
        )

        statistics = {
            "found": len(
                payloads
            ),
            "created": 0,
            "skipped": 0,
            "unresolved": 0,
        }

        for payload in payloads:

            source_reference = (
                payload.get(
                    "source_reference"
                )
            )

            if (
                source_reference
                and source_reference
                in existing_references
            ):

                statistics[
                    "skipped"
                ] += 1

                continue

            entity = (
                self._resolve_entity(
                    payload=payload,
                    entity_by_sender_id=(
                        entity_by_sender_id
                    ),
                    entity_by_name=(
                        entity_by_name
                    ),
                )
            )

            if entity is None:

                statistics[
                    "unresolved"
                ] += 1

            metadata_json = json.dumps(
                payload.get(
                    "metadata",
                    {},
                ),
                ensure_ascii=False,
                default=str,
            )

            self.timeline_service.create_event(
                case_id=case_id,
                entity_id=(
                    entity.id
                    if entity is not None
                    else None
                ),
                event_type=payload[
                    "event_type"
                ],
                title=payload[
                    "title"
                ],
                event_time=payload[
                    "event_time"
                ],
                source_reference=(
                    source_reference
                ),
                metadata_json=(
                    metadata_json
                ),
                description=(
                    "Telegram message "
                    "timeline event"
                ),
            )

            if source_reference:

                existing_references.add(
                    source_reference
                )

            statistics[
                "created"
            ] += 1

        return statistics

    # ==========================================================
    # Entity indexes
    # ==========================================================

    def _build_sender_id_index(
        self,
        entities: list[Entity],
    ) -> dict[str, Entity]:
        """
        Index person entities by
        Telegram sender identifier.
        """

        result: dict[
            str,
            Entity
        ] = {}

        for entity in entities:

            if not self._is_person(
                entity
            ):
                continue

            metadata = (
                self._parse_metadata(
                    entity.metadata_json
                )
            )

            telegram_id = (
                metadata.get(
                    "telegram_id"
                )
                or metadata.get(
                    "sender_id"
                )
            )

            normalized_id = (
                self._normalize_text(
                    telegram_id
                )
            )

            if normalized_id is None:
                continue

            result[
                normalized_id
            ] = entity

        return result

    def _build_name_index(
        self,
        entities: list[Entity],
    ) -> dict[str, Entity]:
        """
        Index person entities by
        normalized display name.
        """

        result: dict[
            str,
            Entity
        ] = {}

        for entity in entities:

            if not self._is_person(
                entity
            ):
                continue

            normalized_name = (
                self._normalize_text(
                    entity.normalized_value
                    or entity.value
                )
            )

            if normalized_name is None:
                continue

            result[
                normalized_name
            ] = entity

        return result

    # ==========================================================
    # Entity resolution
    # ==========================================================

    def _resolve_entity(
        self,
        payload: dict[str, Any],
        entity_by_sender_id: dict[
            str,
            Entity,
        ],
        entity_by_name: dict[
            str,
            Entity,
        ],
    ) -> Entity | None:
        """
        Resolve Telegram author entity.
        """

        sender_id = (
            self._normalize_text(
                payload.get(
                    "sender_id"
                )
            )
        )

        if (
            sender_id is not None
            and sender_id
            in entity_by_sender_id
        ):

            return entity_by_sender_id[
                sender_id
            ]

        author = (
            self._normalize_text(
                payload.get(
                    "author"
                )
            )
        )

        if (
            author is not None
            and author
            in entity_by_name
        ):

            return entity_by_name[
                author
            ]

        return None

    # ==========================================================
    # Helpers
    # ==========================================================

    def _is_person(
        self,
        entity: Entity,
    ) -> bool:
        """
        Check whether entity
        represents a person.
        """

        entity_type = (
            entity.entity_type
        )

        return (
            entity_type
            == EntityType.PERSON
            or str(
                getattr(
                    entity_type,
                    "value",
                    entity_type,
                )
            ).lower()
            == "person"
        )

    def _parse_metadata(
        self,
        metadata_json: str | None,
    ) -> dict[str, Any]:
        """
        Parse entity metadata.
        """

        if not metadata_json:
            return {}

        try:

            value = json.loads(
                metadata_json
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):

            return {}

        if not isinstance(
            value,
            dict,
        ):
            return {}

        return value

    def _normalize_text(
        self,
        value: Any,
    ) -> str | None:
        """
        Normalize identifiers and names.
        """

        if value is None:
            return None

        text = str(
            value
        ).strip().casefold()

        if not text:
            return None

        return text