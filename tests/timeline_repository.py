"""
Timeline repository.

Provides database operations
for timeline events.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.timeline_event import (
    TimelineEvent,
    TimelineEventType,
)

from app.repositories.base_repository import (
    BaseRepository,
)



class TimelineRepository(
    BaseRepository[TimelineEvent],
):
    """
    Repository for timeline events.
    """


    def __init__(
        self,
        session: Session,
    ):
        super().__init__(
            session,
            TimelineEvent,
        )



    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return all events in case.
        """

        result = self.session.execute(
            select(TimelineEvent)
            .where(
                TimelineEvent.case_id == case_id
            )
            .order_by(
                TimelineEvent.event_time
            )
        )

        return list(
            result.scalars().all()
        )



    def get_by_entity(
        self,
        entity_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return events related
        to entity.
        """

        result = self.session.execute(
            select(TimelineEvent)
            .where(
                TimelineEvent.entity_id == entity_id
            )
            .order_by(
                TimelineEvent.event_time
            )
        )

        return list(
            result.scalars().all()
        )



    def get_by_type(
        self,
        event_type: TimelineEventType,
    ) -> list[TimelineEvent]:
        """
        Find events by type.
        """

        result = self.session.execute(
            select(TimelineEvent)
            .where(
                TimelineEvent.event_type == event_type
            )
        )

        return list(
            result.scalars().all()
        )



    def get_between_dates(
        self,
        start: str,
        end: str,
    ) -> list[TimelineEvent]:
        """
        Find events inside time range.
        """

        result = self.session.execute(
            select(TimelineEvent)
            .where(
                TimelineEvent.event_time >= start,
                TimelineEvent.event_time <= end,
            )
            .order_by(
                TimelineEvent.event_time
            )
        )

        return list(
            result.scalars().all()
        )