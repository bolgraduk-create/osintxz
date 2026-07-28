"""
Temporal pattern detector.

Detects suspicious time patterns
inside investigation timelines.
"""

from __future__ import annotations

from datetime import datetime

from app.models.timeline_event import (
    TimelineEvent,
)



class TemporalPatternDetector:
    """
    Detects temporal anomalies.
    """



    def __init__(
        self,
        events: list[TimelineEvent],
    ):
        self.events = sorted(
            events,
            key=lambda e: e.event_time,
        )



    def find_rapid_sequences(
        self,
        minutes: int = 10,
    ) -> list[list[TimelineEvent]]:
        """
        Find groups of events
        happening within short time.
        """

        sequences = []


        current = []


        for event in self.events:

            if not current:
                current.append(
                    event
                )
                continue


            first_time = datetime.fromisoformat(
                current[0].event_time
            )

            current_time = datetime.fromisoformat(
                event.event_time
            )


            diff = (
                current_time - first_time
            ).total_seconds() / 60


            if diff <= minutes:

                current.append(
                    event
                )

            else:

                if len(current) > 1:
                    sequences.append(
                        current
                    )

                current = [
                    event
                ]


        if len(current) > 1:
            sequences.append(
                current
            )


        return sequences