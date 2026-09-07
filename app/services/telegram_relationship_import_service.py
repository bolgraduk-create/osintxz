"""
Telegram relationship import service.

Imports Telegram participant interactions
into investigation relationships.

Pipeline:

CollectedItem objects
        ↓
TelegramInteractionService
        ↓
Relationship candidates
        ↓
Existing PERSON entities
        ↓
RelationshipService
        ↓
PostgreSQL

Responsibilities:

- analyze Telegram reply interactions
- resolve existing Telegram participant entities
- create MESSAGED relationships
- prevent duplicate relationships
- store interaction statistics in metadata

Does NOT:

- parse Telegram exports
- create entities
- perform AI analysis
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

from app.models.relationship import (
    RelationshipType,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.telegram_interaction_service import (
    TelegramInteractionService,
)


class TelegramRelationshipImportService:
    """
    Imports Telegram reply interactions
    as investigation relationships.
    """

    def __init__(
        self,
        relationship_service: RelationshipService,
        interaction_service: TelegramInteractionService,
        entity_service: EntityService,
    ) -> None:

        self.relationship_service = (
            relationship_service
        )

        self.interaction_service = (
            interaction_service
        )

        self.entity_service = (
            entity_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def import_relationships(
        self,
        case_id: UUID,
        items: list[CollectedItem],
    ) -> dict[str, int]:
        """
        Import Telegram relationships into a case.

        Relationships are created only between
        existing PERSON entities.
        """

        candidates = (
            self.interaction_service.analyze(
                items
            )
        )

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

        existing_relationships = (
            self.relationship_service
            .get_case_relationships(
                case_id
            )
        )

        existing_keys = {
            (
                relationship.source_entity_id,
                relationship.target_entity_id,
                relationship.relationship_type,
            )
            for relationship
            in existing_relationships
        }

        created = 0
        skipped = 0
        unresolved = 0

        for candidate in candidates:

            source_entity = (
                self._resolve_entity(
                    sender_id=(
                        candidate.get(
                            "source_sender_id"
                        )
                    ),
                    value=(
                        candidate.get(
                            "source_value"
                        )
                    ),
                    entity_by_sender_id=(
                        entity_by_sender_id
                    ),
                    entity_by_name=(
                        entity_by_name
                    ),
                )
            )

            target_entity = (
                self._resolve_entity(
                    sender_id=(
                        candidate.get(
                            "target_sender_id"
                        )
                    ),
                    value=(
                        candidate.get(
                            "target_value"
                        )
                    ),
                    entity_by_sender_id=(
                        entity_by_sender_id
                    ),
                    entity_by_name=(
                        entity_by_name
                    ),
                )
            )

            if (
                source_entity is None
                or target_entity is None
            ):

                unresolved += 1

                continue

            if (
                source_entity.id
                == target_entity.id
            ):

                skipped += 1

                continue

            relationship_type = (
                RelationshipType.MESSAGED
            )

            relationship_key = (
                source_entity.id,
                target_entity.id,
                relationship_type,
            )

            if relationship_key in existing_keys:

                skipped += 1

                continue

            metadata = (
                self._build_metadata(
                    candidate
                )
            )

            self.relationship_service.create_relationship(
                case_id=case_id,
                source_entity_id=(
                    source_entity.id
                ),
                target_entity_id=(
                    target_entity.id
                ),
                relationship_type=(
                    relationship_type
                ),
                confidence=float(
                    candidate.get(
                        "confidence",
                        0.6,
                    )
                ),
                metadata_json=json.dumps(
                    metadata,
                    ensure_ascii=False,
                    default=str,
                ),
                description=(
                    "Telegram reply interaction"
                ),
            )

            existing_keys.add(
                relationship_key
            )

            created += 1

        return {
            "found": len(
                candidates
            ),
            "created": created,
            "skipped": skipped,
            "unresolved": unresolved,
        }

    # ==========================================================
    # Entity indexes
    # ==========================================================

    def _build_sender_id_index(
        self,
        entities: list[Entity],
    ) -> dict[str, Entity]:
        """
        Index PERSON entities by Telegram sender ID.
        """

        result: dict[
            str,
            Entity,
        ] = {}

        for entity in entities:

            if (
                entity.entity_type
                != EntityType.PERSON
            ):
                continue

            metadata = (
                self._load_metadata(
                    entity.metadata_json
                )
            )

            telegram_id = metadata.get(
                "telegram_id"
            )

            if telegram_id is None:
                continue

            result[
                str(
                    telegram_id
                )
            ] = entity

        return result

    def _build_name_index(
        self,
        entities: list[Entity],
    ) -> dict[str, Entity]:
        """
        Index PERSON entities by normalized name.
        """

        result: dict[
            str,
            Entity,
        ] = {}

        for entity in entities:

            if (
                entity.entity_type
                != EntityType.PERSON
            ):
                continue

            normalized_value = (
                entity.normalized_value
            )

            if not normalized_value:

                normalized_value = (
                    self._normalize_value(
                        entity.value
                    )
                )

            if not normalized_value:
                continue

            result[
                self._normalize_value(
                    normalized_value
                )
            ] = entity

        return result

    # ==========================================================
    # Entity resolution
    # ==========================================================

    def _resolve_entity(
        self,
        sender_id: Any,
        value: Any,
        entity_by_sender_id: dict[str, Entity],
        entity_by_name: dict[str, Entity],
    ) -> Entity | None:
        """
        Resolve an existing PERSON entity.

        Telegram sender ID has priority.
        Name matching is used as fallback.
        """

        if sender_id is not None:

            entity = (
                entity_by_sender_id.get(
                    str(
                        sender_id
                    )
                )
            )

            if entity is not None:
                return entity

        if value is None:
            return None

        normalized_value = (
            self._normalize_value(
                str(
                    value
                )
            )
        )

        return entity_by_name.get(
            normalized_value
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def _build_metadata(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build relationship metadata.
        """

        dates = [
            serialized
            for value in candidate.get(
                "dates",
                []
            )
            if (
                serialized := (
                    self._serialize_date(
                        value
                    )
                )
            )
            is not None
        ]

        return {
            "source": "telegram",
            "detection_method": (
                "reply_reference"
            ),
            "frequency": int(
                candidate.get(
                    "frequency",
                    0,
                )
            ),
            "strength": float(
                candidate.get(
                    "strength",
                    0.0,
                )
            ),
            "source_sender_id": (
                candidate.get(
                    "source_sender_id"
                )
            ),
            "target_sender_id": (
                candidate.get(
                    "target_sender_id"
                )
            ),
            "source_value": (
                candidate.get(
                    "source_value"
                )
            ),
            "target_value": (
                candidate.get(
                    "target_value"
                )
            ),
            "dates": dates,
        }

    def _load_metadata(
        self,
        metadata_json: str | None,
    ) -> dict[str, Any]:
        """
        Deserialize entity metadata safely.
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

    def _serialize_date(
        self,
        value: Any,
    ) -> str | None:
        """
        Convert interaction date into a JSON-safe string.
        """

        if value is None:
            return None

        isoformat = getattr(
            value,
            "isoformat",
            None,
        )

        if callable(
            isoformat
        ):

            return isoformat()

        return str(
            value
        )

    # ==========================================================
    # Normalization
    # ==========================================================

    def _normalize_value(
        self,
        value: Any,
    ) -> str:
        """
        Normalize participant name.
        """

        if value is None:
            return ""

        return " ".join(
            str(
                value
            )
            .strip()
            .lower()
            .split()
        )