"""
Telegram timeline service.

Builds chronological Telegram events.

Responsibilities:

- build chronological events
- prepare timeline entries
- sort events

Does NOT:

- create Timeline model
- AI analysis
- relationship analysis
"""

from __future__ import annotations

from datetime import datetime


class TelegramTimelineService:
    """
    Telegram timeline builder.
    """

    def build(
        self,
        messages,
    ) -> list[dict]:
        """
        Build chronological events.
        """

        events = []

        for message in messages:

            date = getattr(
                message,
                "date",
                None,
            )

            if not isinstance(
                date,
                datetime,
            ):
                continue

            sender = getattr(
                message,
                "sender",
                None,
            )

            text = getattr(
                message,
                "text",
                "",
            )

            events.append(

                {
                    "timestamp": date,
                    "sender": sender,
                    "text": text,
                }

            )

        events.sort(
            key=lambda item:
            item["timestamp"]
        )

        return events

    def first_event(
        self,
        messages,
    ):

        events = self.build(
            messages
        )

        if not events:
            return None

        return events[0]

    def last_event(
        self,
        messages,
    ):

        events = self.build(
            messages
        )

        if not events:
            return None

        return events[-1]