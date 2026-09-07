"""
Case workspace application service.

Responsible for:

- preparing investigation workspace data
- aggregating case information
- providing UI-ready workspace state

Does NOT:

- access database directly
- contain UI logic
- perform analysis
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.case_service import (
    CaseService,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.entity_graph_service import (
    EntityGraphService,
)

from app.services.message_service import (
    MessageService,
)

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.report_service import (
    ReportService,
)

from app.services.timeline_service import (
    TimelineService,
)

from app.models.entity import (
    EntityType,
)


class CaseWorkspaceService:
    """
    Application service for case workspace.
    """

    def __init__(
        self,
        case_service: CaseService,
        evidence_service: EvidenceService,
        entity_service: EntityService,
        entity_graph_service: EntityGraphService,
        message_service: MessageService,
        relationship_service: RelationshipService,
        timeline_service: TimelineService,
        report_service: ReportService,
    ) -> None:

        self.case_service = case_service

        self.evidence_service = evidence_service

        self.entity_service = entity_service

        self.entity_graph_service = (
            entity_graph_service
        )

        self.message_service = message_service

        self.relationship_service = (
            relationship_service
        )

        self.timeline_service = timeline_service

        self.report_service = report_service

    # ==========================================================
    # Workspace
    # ==========================================================

    def get_workspace(
        self,
        case_id: str | UUID,
    ) -> dict[str, Any] | None:
        """
        Build complete workspace data for UI.
        """

        case_uuid = self._normalize_case_id(
            case_id
        )

        case = self.case_service.get_case(
            case_uuid
        )

        if case is None:
            return None

        messages = (
            self.message_service
            .get_case_messages(
                case_uuid
            )
        )

        evidence_list = (
            self.evidence_service
            .get_case_evidence(
                case_uuid
            )
        )

        entity_list = (
            self.entity_service
            .get_case_entities(
                case_uuid
            )
        )

        relationship_list = (
            self.relationship_service
            .get_case_relationships(
                case_uuid
            )
        )

        timeline_list = (
            self.timeline_service
            .get_case_timeline(
                case_uuid
            )
        )

        report_list = (
            self.report_service
            .get_case_reports(
                case_uuid
            )
        )

        graph_data = (
            self.entity_graph_service
            .get_case_graph_data(
                case_uuid
            )
        )

        return {
            "case": {
                "id": str(
                    case.id
                ),
                "title": case.title,
                "description": (
                    case.description
                ),
            },

            "statistics": {
                "messages": len(
                    messages
                ),
                "evidence": len(
                    evidence_list
                ),
                "entities": len(
                    entity_list
                ),
                "relationships": len(
                    relationship_list
                ),
                "reports": len(
                    report_list
                ),
                "timeline": len(
                    timeline_list
                ),
            },

            "messages": [
                self._serialize_message(
                    message
                )
                for message in messages
            ],

            "evidence": [
                {
                    "id": str(
                        item.id
                    ),
                    "case_id": str(
                        item.case_id
                    ),
                    "source_id": (
                        str(
                            item.source_id
                        )
                        if item.source_id
                        else None
                    ),
                    "title": item.title,
                    "description": (
                        item.description
                    ),
                    "type": (
                        item.evidence_type.value
                    ),
                    "value": item.value,
                    "file_path": (
                        item.file_path
                    ),
                    "mime_type": (
                        item.mime_type
                    ),
                    "sha256": (
                        item.sha256
                    ),
                    "metadata_json": (
                        item.metadata_json
                    ),
                    "created_at": (
                        item.created_at.isoformat()
                        if item.created_at
                        else None
                    ),
                    "updated_at": (
                        item.updated_at.isoformat()
                        if item.updated_at
                        else None
                    ),
                }
                for item in evidence_list
            ],

            "entities": [
                {
                    "id": str(
                        item.id
                    ),
                    "case_id": str(
                        item.case_id
                    ),
                    "type": (
                        item.entity_type.value
                    ),
                    "value": item.value,
                    "normalized_value": (
                        item.normalized_value
                    ),
                    "confidence": (
                        item.confidence
                    ),
                    "metadata_json": (
                        item.metadata_json
                    ),
                    "description": (
                        item.description
                    ),
                    "created_at": (
                        item.created_at.isoformat()
                        if item.created_at
                        else None
                    ),
                    "updated_at": (
                        item.updated_at.isoformat()
                        if item.updated_at
                        else None
                    ),
                }
                for item in entity_list
            ],

            "relationships": [
                {
                    "id": str(
                        item.id
                    ),
                    "type": (
                        item
                        .relationship_type
                        .value
                    ),
                    "source": str(
                        item.source_entity_id
                    ),
                    "target": str(
                        item.target_entity_id
                    ),
                    "confidence": (
                        item.confidence
                    ),
                }
                for item in relationship_list
            ],

            "timeline": [
                {
                    "id": str(
                        item.id
                    ),
                    "title": item.title,
                    "date": str(
                        item.event_time
                    ),
                    "type": (
                        item.event_type.value
                    ),
                    "description": (
                        item.description
                    ),
                }
                for item in timeline_list
            ],

            "reports": [
                {
                    "id": str(
                        item.id
                    ),
                    "title": item.title,
                    "content": (
                        item.content
                    ),
                    "type": (
                        item.report_type.value
                    ),
                }
                for item in report_list
            ],

            "graph": graph_data,
        }

    # ==========================================================
    # Workspace actions
    # ==========================================================

    def create_evidence_from_message(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
    ):
        """
        Create evidence from a workspace message.
        """

        case_uuid = self._normalize_case_id(
            case_id
        )

        evidence = (
            self.evidence_service
            .create_from_message(
                case_id=case_uuid,
                message_data=message_data,
            )
        )

        return {
            "evidence": {
                "id": str(
                    evidence.id
                ),
                "title": evidence.title,
                "type": (
                    evidence.evidence_type.value
                ),
                "value": evidence.value,
            }
        }

    def create_entity_from_message(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
        field_name: str,
        entity_type: str | EntityType,
    ) -> dict[str, Any]:
        """
        Create or reuse an entity from one message field.
        """

        case_uuid = self._normalize_case_id(
            case_id
        )

        if isinstance(
            entity_type,
            EntityType,
        ):

            normalized_entity_type = (
                entity_type
            )

        else:

            try:

                normalized_entity_type = (
                    EntityType(
                        str(
                            entity_type
                        ).strip().lower()
                    )
                )

            except ValueError as error:

                raise ValueError(
                    "Unsupported entity type."
                ) from error

        (
            entity,
            created,
        ) = (
            self.entity_service
            .create_from_message_field(
                case_id=case_uuid,
                message_data=message_data,
                field_name=field_name,
                entity_type=normalized_entity_type,
            )
        )

        return {
            "entity": {
                "id": str(
                    entity.id
                ),
                "type": (
                    entity.entity_type.value
                ),
                "value": entity.value,
                "normalized_value": (
                    entity.normalized_value
                ),
                "confidence": (
                    entity.confidence
                ),
            },
            "created": created,
        }

    def create_timeline_from_message(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a timeline event from one message.
        """

        case_uuid = self._normalize_case_id(
            case_id
        )

        event = (
            self.timeline_service
            .create_from_message(
                case_id=case_uuid,
                message_data=message_data,
            )
        )

        return {
            "timeline_event": {
                "id": str(
                    event.id
                ),
                "title": event.title,
                "type": (
                    event.event_type.value
                ),
                "event_time": (
                    event.event_time
                ),
            }
        }

    # ==========================================================
    # Serialization
    # ==========================================================

    def _serialize_message(
        self,
        message,
    ) -> dict[str, Any]:
        """
        Convert Message model into UI-ready data.
        """

        return {
            "id": str(
                message.id
            ),
            "source_id": str(
                message.source_id
            ),
            "evidence_id": (
                str(
                    message.evidence_id
                )
                if message.evidence_id
                else None
            ),
            "external_id": (
                message.external_id
            ),
            "sender": (
                message.sender
            ),
            "receiver": (
                message.receiver
            ),
            "chat_name": (
                message.chat_name
            ),
            "sent_at": (
                message.sent_at.isoformat()
                if message.sent_at
                else None
            ),
            "text": (
                message.text
                or ""
            ),
            "reply_to_id": (
                str(
                    message.reply_to_id
                )
                if message.reply_to_id
                else None
            ),
            "metadata_json": (
                message.metadata_json
            ),
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    def _normalize_case_id(
        self,
        case_id: str | UUID,
    ) -> UUID:
        """
        Convert case identifier to UUID.
        """

        if isinstance(
            case_id,
            UUID,
        ):
            return case_id

        return UUID(
            str(
                case_id
            )
        )