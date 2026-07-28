"""
Timeline analyzer.

Provides analytical operations
over investigation timeline.
"""

from __future__ import annotations

from uuid import UUID

from app.models.timeline_event import (
    TimelineEvent,
)



class TimelineAnalyzer:
    """
    Analyzer for timeline events.
    """



    def __init__(
        self,
        events: list[TimelineEvent],
    ):
        self.events = events



    def count_events(
        self,
    ) -> int:
        """
        Count total events.
        """

        return len(
            self.events
        )



    def get_entity_activity(
        self,
        entity_id: UUID,
    ) -> list[TimelineEvent]:
        """
        Return events of entity.
        """

        return [
            event
            for event in self.events
            if event.entity_id == entity_id
        ]



    def get_first_event(
        self,
    ) -> TimelineEvent | None:
        """
        Return earliest event.
        """

        if not self.events:
            return None


        return sorted(
            self.events,
            key=lambda e: e.event_time,
        )[0]



    def get_last_event(
        self,
    ) -> TimelineEvent | None:
        """
        Return latest event.
        """

        if not self.events:
            return None


        return sorted(
            self.events,
            key=lambda e: e.event_time,
        )[-1]



    def get_activity_range(
        self,
    ) -> tuple[str, str] | None:
        """
        Return activity period.
        """

        first = self.get_first_event()

        last = self.get_last_event()


        if first is None or last is None:
            return None


        return (
            first.event_time,
            last.event_time,
        )