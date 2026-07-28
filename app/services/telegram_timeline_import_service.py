"""
Telegram timeline import service.

Imports Telegram events into investigation timeline.

Responsibilities:

- convert Telegram timeline
- import chronological events
- preserve event ordering

Does NOT:

- parse Telegram exports
- perform AI analysis
- create entities
"""

from __future__ import annotations

from uuid import UUID

from app.services.timeline_service import (
    TimelineService,
)

from app.services.telegram_timeline_service import (
    TelegramTimelineService,
)


class TelegramTimelineImportService:
    """
    Imports Telegram timeline into investigation.
    """

    def __init__(
        self,
        timeline_service: TimelineService,
        telegram_timeline_service: TelegramTimelineService,
    ):

        self.timeline_service = timeline_service

        self.telegram_timeline_service = (
            telegram_timeline_service
        )

    def import_timeline(
        self,
        case_id: UUID,
        messages,
    ) -> None:
        """
        Import Telegram events into investigation timeline.
        """

        events = (
            self.telegram_timeline_service.build(
                messages
            )
        )

        for event in events:

            self.timeline_service.create(
                case_id=case_id,
                timestamp=event["timestamp"],
                title="Telegram Message",
                description=event["text"],
                metadata={
                    "sender": event["sender"],
                    "source": "telegram",
                },
            )