"""
Entity service.

Contains business logic related
to extracted entities.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entity import (
    Entity,
    EntityType,
)

from app.entity_resolution.normalizer import (
    EntityNormalizer,
)

from app.repositories.entity_repository import (
    EntityRepository,
)



class EntityService:
    """
    Service for managing entities.
    """

    def __init__(
        self,
        session: Session,
        *,
        normalizer: EntityNormalizer | None = None,
    ) -> None:

        self.repository = EntityRepository(
            session
        )

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

    # ==========================================================
    # CRUD
    # ==========================================================

    def create_entity(
        self,
        case_id: UUID,
        entity_type: EntityType,
        value: str,
        normalized_value: str | None = None,
        confidence: float = 1.0,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> Entity:
        """
        Create an entity using the shared normalization contract.

        If a caller supplies a specialized normalized_value, that
        value is preserved as the normalization source and passed
        through EntityNormalizer for canonical formatting.

        If normalized_value is omitted or blank, the canonical value
        is derived directly from the entity display value.
        """

        normalization_source = (
            normalized_value
            if (
                normalized_value is not None
                and str(normalized_value).strip()
            )
            else value
        )

        canonical_normalized_value = (
            self._normalize_entity_value(
                value=str(
                    normalization_source
                ),
                entity_type=entity_type,
            )
        )

        entity = Entity(
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            normalized_value=(
                canonical_normalized_value
            ),
            confidence=confidence,
            metadata_json=metadata_json,
            description=description,
        )

        return self.repository.create(
            entity
        )

    def resolve_existing_entity(
        self,
        *,
        case_id: str | UUID,
        entity_type: EntityType,
        value: str,
        normalized_value: str | None = None,
    ) -> Entity | None:
        """
        Resolve an exact logical Entity inside one case.

        The lookup key is always produced by the shared
        EntityNormalizer before repository access. This prevents
        extraction-specific formatting from becoming a second,
        competing identity contract.

        This method performs exact canonical resolution only. It does
        not run fuzzy identity scoring and does not merge entities.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        normalization_source = (
            normalized_value
            if (
                normalized_value is not None
                and str(normalized_value).strip()
            )
            else value
        )

        canonical_normalized_value = self._normalize_entity_value(
            value=str(normalization_source),
            entity_type=entity_type,
        )

        if not canonical_normalized_value:
            return None

        return self.repository.find_in_case(
            case_id=case_uuid,
            entity_type=entity_type,
            normalized_value=canonical_normalized_value,
        )

    def resolve_or_create_entity(
        self,
        *,
        case_id: str | UUID,
        entity_type: EntityType,
        value: str,
        normalized_value: str | None = None,
        confidence: float = 1.0,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> tuple[Entity, bool]:
        """
        Resolve an exact canonical Entity or create it once.

        Returns:
            tuple[Entity, bool]:
                ``(entity, True)`` when a new Entity was created,
                otherwise ``(existing_entity, False)``.

        The normalization used for lookup is exactly the same
        normalization used for persistence. Fuzzy Entity Resolution
        remains a separate read-only analysis pipeline and is never
        invoked implicitly from extraction.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        normalization_source = (
            normalized_value
            if (
                normalized_value is not None
                and str(normalized_value).strip()
            )
            else value
        )

        canonical_normalized_value = self._normalize_entity_value(
            value=str(normalization_source),
            entity_type=entity_type,
        )

        if not canonical_normalized_value:
            raise ValueError(
                "Entity normalized value cannot be empty."
            )

        existing = self.repository.find_in_case(
            case_id=case_uuid,
            entity_type=entity_type,
            normalized_value=canonical_normalized_value,
        )

        if existing is not None:
            return existing, False

        entity = self.create_entity(
            case_id=case_uuid,
            entity_type=entity_type,
            value=value,
            normalized_value=canonical_normalized_value,
            confidence=confidence,
            metadata_json=metadata_json,
            description=description,
        )

        return entity, True

    def create_from_message_field(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
        field_name: str,
        entity_type: EntityType,
    ) -> tuple[Entity, bool]:
        """
        Create an entity from one message field.

        Returns:
            tuple[Entity, bool]:
                Entity object and whether it was newly created.
        """

        if not isinstance(
            message_data,
            dict,
        ):

            raise TypeError(
                "message_data must be a dictionary"
            )

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        normalized_field_name = str(
            field_name
        ).strip().lower()

        allowed_fields = {
            "sender",
            "receiver",
            "chat_name",
        }

        if (
            normalized_field_name
            not in allowed_fields
        ):

            raise ValueError(
                "Unsupported message entity field."
            )

        raw_value = message_data.get(
            normalized_field_name
        )

        value = self._normalize_text(
            raw_value
        )

        if not value:

            raise ValueError(
                "The selected message field is empty."
            )

        normalized_value = (
            self._normalize_entity_value(
                value=value,
                entity_type=entity_type,
            )
        )

        existing_entity = (
            self.repository.find_in_case(
                case_id=case_uuid,
                entity_type=entity_type,
                normalized_value=(
                    normalized_value
                ),
            )
        )

        if existing_entity is not None:

            return (
                existing_entity,
                False,
            )

        description = (
            self._build_message_entity_description(
                message_data=message_data,
                field_name=(
                    normalized_field_name
                ),
            )
        )

        entity = self.create_entity(
            case_id=case_uuid,
            entity_type=entity_type,
            value=value,
            normalized_value=(
                normalized_value
            ),
            confidence=1.0,
            description=description,
        )

        return (
            entity,
            True,
        )

    # ==========================================================
    # Retrieval
    # ==========================================================

    def get_entity(
        self,
        entity_id: str | UUID,
    ) -> Entity | None:

        normalized_entity_id = (
            self._normalize_uuid(
                entity_id,
                field_name="entity_id",
            )
        )

        return self.repository.get(
            normalized_entity_id
        )

    def get_case_entities(
        self,
        case_id: str | UUID,
    ) -> list[Entity]:

        normalized_case_id = (
            self._normalize_uuid(
                case_id,
                field_name="case_id",
            )
        )

        return self.repository.get_by_case(
            normalized_case_id
        )

    def get_page(self, *, limit: int = 100, offset: int = 0, case_id: UUID | None = None):
        return self.repository.get_page(limit=limit, offset=offset, case_id=case_id)

    def count_all(self, *, case_id: UUID | None = None) -> int:
        return self.repository.count_all(case_id=case_id)

    def find_by_value(
        self,
        value: str,
    ) -> list[Entity]:

        return self.repository.find_by_value(
            value
        )

    # ==========================================================
    # Updates
    # ==========================================================

    def update_entity(
        self,
        entity_id: str | UUID,
        *,
        value: str | None = None,
        description: str | None = None,
        metadata_json: str | None = None,
    ) -> Entity | None:
        """
        Update editable entity fields.

        When value is changed, normalized_value is
        recalculated automatically.

        For LOCATION entities, callers should normally
        preserve value/normalized_value because they may
        represent the geographic identity of the entity.
        User-facing marker names belong in metadata_json.
        """

        normalized_entity_id = (
            self._normalize_uuid(
                entity_id,
                field_name="entity_id",
            )
        )

        entity = self.repository.get(
            normalized_entity_id
        )

        if entity is None:

            return None

        if value is not None:

            normalized_value_text = (
                self._normalize_text(
                    value
                )
            )

            if not normalized_value_text:

                raise ValueError(
                    "Entity value cannot be empty."
                )

            entity.value = (
                normalized_value_text
            )

            entity.normalized_value = (
                self._normalize_entity_value(
                    value=(
                        normalized_value_text
                    ),
                    entity_type=(
                        entity.entity_type
                    ),
                )
            )

        if description is not None:

            entity.description = str(
                description
            ).strip()

        if metadata_json is not None:

            entity.metadata_json = str(
                metadata_json
            )

        self.repository.session.flush()

        return entity

    def update_metadata(
        self,
        entity_id: str | UUID,
        metadata_json: str,
    ) -> Entity | None:
        """
        Update entity metadata JSON.
        """

        return self.update_entity(
            entity_id,
            metadata_json=metadata_json,
        )

    def update_description(
        self,
        entity_id: str | UUID,
        description: str,
    ) -> Entity | None:
        """
        Update entity description.
        """

        return self.update_entity(
            entity_id,
            description=description,
        )

    def update_confidence(
        self,
        entity_id: str | UUID,
        confidence: float,
    ) -> Entity | None:

        normalized_entity_id = (
            self._normalize_uuid(
                entity_id,
                field_name="entity_id",
            )
        )

        entity = self.repository.get(
            normalized_entity_id
        )

        if entity is None:

            return None

        normalized_confidence = float(
            confidence
        )

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):

            raise ValueError(
                "Entity confidence must be "
                "between 0.0 and 1.0."
            )

        entity.confidence = (
            normalized_confidence
        )

        self.repository.session.flush()

        return entity

    # ==========================================================
    # Deletion
    # ==========================================================

    def delete_entity(
        self,
        entity_id: str | UUID,
    ) -> bool:

        normalized_entity_id = (
            self._normalize_uuid(
                entity_id,
                field_name="entity_id",
            )
        )

        entity = self.repository.get(
            normalized_entity_id
        )

        if entity is None:

            return False

        entity.soft_delete()

        self.repository.session.flush()

        return True

    # ==========================================================
    # Processing
    # ==========================================================

    def process_case(
        self,
        case_id: UUID,
    ) -> dict[str, Any]:
        """
        Backward-compatible entity extraction entry point.

        Extraction orchestration now belongs to
        UnifiedExtractionService. Existing callers can continue using
        EntityService.process_case() while new workflows should depend
        on UnifiedExtractionService directly.
        """

        from app.processing.extraction import IdentifierExtractor
        from app.services.unified_extraction_service import (
            UnifiedExtractionService,
        )

        extraction_service = UnifiedExtractionService(
            session=self.repository.session,
            entity_service=self,
            identifier_extractor=IdentifierExtractor(
                normalizer=self.normalizer,
            ),
        )

        return extraction_service.extract_case_messages(
            case_id=case_id,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Convert an identifier to UUID.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain "
                "a valid UUID."
            ) from error

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:
        """
        Convert an optional value to stripped text.
        """

        if value is None:

            return ""

        return str(
            value
        ).strip()

    def _normalize_entity_value(
        self,
        *,
        value: str,
        entity_type: EntityType,
    ) -> str:
        """
        Normalize an entity value through the shared
        EntityNormalizer contract.

        This method remains as the EntityService-local adapter so
        existing callers and service boundaries stay stable while the
        normalization implementation has a single source of truth.
        """

        return self.normalizer.normalize(
            entity_type,
            value,
        )

    @staticmethod
    def _build_message_entity_description(
        *,
        message_data: dict[str, Any],
        field_name: str,
    ) -> str:
        """
        Build provenance information for a
        message-derived entity.
        """

        message_id = str(
            message_data.get(
                "id"
            )
            or ""
        )

        external_id = str(
            message_data.get(
                "external_id"
            )
            or ""
        )

        sent_at = str(
            message_data.get(
                "sent_at"
            )
            or ""
        )

        chat_name = str(
            message_data.get(
                "chat_name"
            )
            or ""
        )

        return (
            "Entity created from message.\n\n"
            f"Field: {field_name}\n"
            f"Message ID: "
            f"{message_id or 'Unavailable'}\n"
            f"External ID: "
            f"{external_id or 'Unavailable'}\n"
            f"Date: "
            f"{sent_at or 'Unavailable'}\n"
            f"Chat: "
            f"{chat_name or 'Unavailable'}"
        )
