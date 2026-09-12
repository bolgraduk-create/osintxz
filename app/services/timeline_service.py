"""
Timeline service.

Contains business logic
for investigation timeline events.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session


from app.models.timeline_event import (
    TimelineEvent,
    TimelineEventType,
)


from app.repositories.timeline_repository import (
    TimelineRepository,
)



class TimelineService:
    """
    Service for timeline events.
    """



    def __init__(
        self,
        session: Session,
    ):
        self.repository = TimelineRepository(
            session
        )



    def create_event(
        self,
        case_id: UUID,
        event_type: TimelineEventType,
        title: str,
        event_time: str,
        entity_id: UUID | None = None,
        source_reference: str | None = None,
        metadata_json: str | None = None,
        description: str | None = None,
    ) -> TimelineEvent:
        """
        Create timeline event.
        """

        event = TimelineEvent(
            case_id=case_id,
            entity_id=entity_id,
            event_type=event_type,
            title=title,
            event_time=event_time,
            source_reference=source_reference,
            metadata_json=metadata_json,
            description=description,
        )


        return self.repository.create(
            event
        )

    def create_from_message(
        self,
        case_id: str | UUID,
        message_data: dict[str, Any],
    ) -> TimelineEvent:
        """
        Create a timeline event from one message.
        """

        if not isinstance(
            message_data,
            dict,
        ):
            raise TypeError(
                "message_data must be a dictionary."
            )

        case_uuid = self._normalize_uuid(
            case_id
        )

        sent_at = self._normalize_text(
            message_data.get(
                "sent_at"
            )
        )

        if not sent_at:
            raise ValueError(
                "Message does not contain a timestamp."
            )

        sender = self._normalize_text(
            message_data.get(
                "sender"
            )
        )

        receiver = self._normalize_text(
            message_data.get(
                "receiver"
            )
        )

        chat = self._normalize_text(
            message_data.get(
                "chat_name"
            )
        )

        message_text = self._normalize_text(
            message_data.get(
                "text"
            )
        )

        title = (
            f"Message from {sender or 'Unknown'}"
        )[:255]

        description = (
            "Timeline event created from message.\n\n"
            f"Sender: {sender or 'Unavailable'}\n"
            f"Receiver: {receiver or 'Unavailable'}\n"
            f"Chat: {chat or 'Unavailable'}\n\n"
            f"{message_text}"
        )

        return self.create_event(
            case_id=case_uuid,
            event_type=TimelineEventType.MESSAGE,
            title=title,
            event_time=sent_at,
            source_reference=str(
                message_data.get(
                    "id"
                )
                or ""
            ),
            description=description,
        )



    def get_event(
        self,
        event_id: UUID,
    ) -> TimelineEvent | None:
        """
        Get event by id.
        """

        return self.repository.get(
            event_id
        )



    def get_case_timeline(
        self,
        case_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return case timeline.
        """

        return self.repository.get_by_case(
            case_id
        )

    def get_page(self, *, limit: int = 100, offset: int = 0, case_id: UUID | None = None):
        return self.repository.get_page(limit=limit, offset=offset, case_id=case_id)

    def count_all(self, *, case_id: UUID | None = None) -> int:
        return self.repository.count_all(case_id=case_id)



    def get_entity_timeline(
        self,
        entity_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return entity timeline.
        """

        return self.repository.get_by_entity(
            entity_id
        )



    def update_metadata(
        self,
        event_id: UUID,
        metadata_json: str,
    ) -> TimelineEvent | None:
        """
        Update event metadata.
        """

        event = self.repository.get(
            event_id
        )


        if event is None:
            return None


        event.metadata_json = metadata_json


        self.repository.session.flush()


        return event



    def delete_event(
        self,
        event_id: UUID,
    ) -> bool:
        """
        Soft delete event.
        """

        event = self.repository.get(
            event_id
        )


        if event is None:
            return False


        event.soft_delete()


        self.repository.session.flush()


        return True

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
    ) -> UUID:

        if isinstance(
            value,
            UUID,
        ):
            return value

        return UUID(
            str(
                value
            )
        )

    @staticmethod
    def _normalize_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        return str(
            value
        ).strip()
