"""
Telegram entity import service.

Imports Telegram participants
into an investigation.

Responsibilities:

- map Telegram participants
- send entity payloads to EntityService
- prevent duplicate import
- serialize entity metadata
- use shared entity normalization contract

Does NOT:

- parse Telegram exports
- perform AI analysis
- create relationships
- perform fuzzy identity resolution
"""

from __future__ import annotations

import json

from uuid import UUID

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.models.entity import (
    EntityType,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.telegram_entity_mapper_service import (
    TelegramEntityMapperService,
)


class TelegramEntityImportService:
    """
    Imports Telegram participants
    into investigation entities.
    """

    def __init__(
        self,
        entity_service: EntityService,
        mapper: TelegramEntityMapperService,
    ) -> None:

        self.entity_service = (
            entity_service
        )

        self.mapper = mapper

        self.normalizer = (
            getattr(
                mapper,
                "normalizer",
                None,
            )
            or EntityNormalizer()
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def import_entities(
        self,
        case_id: UUID,
        items,
    ) -> dict[str, int]:
        """
        Import Telegram participants
        as EntityType.PERSON entities.

        Returns import statistics.
        """

        mapped_entities = (
            self.mapper
            .participants_to_entities(
                items
            )
        )

        existing_entities = (
            self.entity_service
            .get_case_entities(
                case_id
            )
        )

        existing_keys = {
            self._build_existing_key(
                entity.entity_type,
                (
                    entity.normalized_value
                    or entity.value
                ),
            )
            for entity in existing_entities
        }

        created = 0
        skipped = 0

        for payload in mapped_entities:

            entity_type = (
                self._resolve_entity_type(
                    payload.get(
                        "entity_type"
                    )
                )
            )

            value = str(
                payload.get(
                    "value",
                    "",
                )
            ).strip()

            supplied_normalized_value = (
                payload.get(
                    "normalized_value"
                )
            )

            normalization_source = (
                supplied_normalized_value
                if supplied_normalized_value
                is not None
                else value
            )

            normalized_value = (
                self.normalizer.normalize(
                    entity_type,
                    normalization_source,
                )
            )

            if (
                not value
                or not normalized_value
            ):

                skipped += 1

                continue

            existing_key = (
                self._build_existing_key(
                    entity_type,
                    normalized_value,
                )
            )

            if existing_key in existing_keys:

                skipped += 1

                continue

            metadata = (
                payload.get(
                    "metadata"
                )
                or {}
            )

            metadata_json = json.dumps(
                metadata,
                ensure_ascii=False,
                default=str,
            )

            self.entity_service.create_entity(
                case_id=case_id,
                entity_type=entity_type,
                value=value,
                normalized_value=(
                    normalized_value
                ),
                confidence=float(
                    payload.get(
                        "confidence",
                        1.0,
                    )
                ),
                metadata_json=(
                    metadata_json
                ),
                description=(
                    payload.get(
                        "description"
                    )
                ),
            )

            existing_keys.add(
                existing_key
            )

            created += 1

        return {
            "found": len(
                mapped_entities
            ),
            "created": created,
            "skipped": skipped,
        }

    # ==========================================================
    # Entity type
    # ==========================================================

    def _resolve_entity_type(
        self,
        value,
    ) -> EntityType:
        """
        Convert mapper value into EntityType.
        """

        if isinstance(
            value,
            EntityType,
        ):

            return value

        if value is None:

            return EntityType.OTHER

        try:

            return EntityType(
                str(
                    value
                )
                .strip()
                .lower()
            )

        except ValueError:

            return EntityType.OTHER

    # ==========================================================
    # Duplicate handling
    # ==========================================================

    def _build_existing_key(
        self,
        entity_type: EntityType,
        value: str,
    ) -> tuple[EntityType, str]:
        """
        Build duplicate comparison key
        using shared canonical normalization.
        """

        return (
            entity_type,
            self.normalizer.normalize(
                entity_type,
                value,
            ),
        )

    def _normalize_value(
        self,
        value: str,
    ) -> str:
        """
        Backward-compatible PERSON
        normalization helper.

        Delegates to shared EntityNormalizer.
        """

        return self.normalizer.normalize(
            EntityType.PERSON,
            value,
        )