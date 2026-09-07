"""
Timeline repository.

Provides persistence operations
for investigation timeline events.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.timeline_event import (
    TimelineEvent,
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
    ) -> None:

        super().__init__(
            session=session,
            model=TimelineEvent,
        )

    # ==========================================================
    # Queries
    # ==========================================================

    def get_by_case(
        self,
        case_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return timeline events
        belonging to a case.
        """

        statement = (
            select(
                TimelineEvent
            )
            .where(
                TimelineEvent.case_id
                == case_id,
            )
            .order_by(
                TimelineEvent.event_time,
            )
        )

        return list(
            self.session.scalars(
                statement,
            ).all()
        )

    def get_by_entity(
        self,
        entity_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return timeline events
        belonging to an entity.
        """

        statement = (
            select(
                TimelineEvent
            )
            .where(
                TimelineEvent.entity_id
                == entity_id,
            )
            .order_by(
                TimelineEvent.event_time,
            )
        )

        return list(
            self.session.scalars(
                statement,
            ).all()
        )

    # ==========================================================
    # CRUD helpers
    # ==========================================================

    def create(
        self,
        timeline_event: TimelineEvent,
    ) -> TimelineEvent:
        """
        Persist timeline event.

        Transaction commit is handled
        by the application boundary.
        """

        self.session.add(
            timeline_event,
        )

        self.session.flush()

        return timeline_event