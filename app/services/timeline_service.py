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