"""
Telegram analysis service.

Coordinates all Telegram intelligence modules.

Responsibilities:

- participant statistics
- activity analysis
- keyword extraction
- conversation detection
- interaction analysis
- attachment analysis
- timeline analysis

Does NOT:

- import Telegram exports
- create entities
- create relationships
- generate AI reports
"""

from __future__ import annotations

from app.services.telegram_activity_service import (
    TelegramActivityService,
)

from app.services.telegram_attachment_service import (
    TelegramAttachmentService,
)

from app.services.telegram_conversation_service import (
    TelegramConversationService,
)

from app.services.telegram_intelligence_service import (
    TelegramIntelligenceService,
)

from app.services.telegram_interaction_service import (
    TelegramInteractionService,
)

from app.services.telegram_keyword_service import (
    TelegramKeywordService,
)

from app.services.telegram_timeline_service import (
    TelegramTimelineService,
)


class TelegramAnalysisService:
    """
    High-level Telegram intelligence coordinator.
    """

    def __init__(self):

        self.intelligence = (
            TelegramIntelligenceService()
        )

        self.activity = (
            TelegramActivityService()
        )

        self.keywords = (
            TelegramKeywordService()
        )

        self.conversations = (
            TelegramConversationService()
        )

        self.interactions = (
            TelegramInteractionService()
        )

        self.attachments = (
            TelegramAttachmentService()
        )

        self.timeline = (
            TelegramTimelineService()
        )

    def analyze(
        self,
        messages,
    ) -> dict:
        """
        Run complete Telegram analysis.
        """

        conversations = (
            self.conversations.build(
                messages
            )
        )

        return {

            "statistics":
                self.intelligence.statistics(
                    messages
                ),

            "keywords":
                self.keywords.extract(
                    messages
                ),

            "activity_by_day":
                self.activity.activity_by_day(
                    messages
                ),

            "activity_by_hour":
                self.activity.activity_by_hour(
                    messages
                ),

            "activity_by_weekday":
                self.activity.activity_by_weekday(
                    messages
                ),

            "conversation_count":
                len(conversations),

            "largest_conversation":
                self.conversations.largest(
                    conversations
                ),

            "interaction_matrix":
                self.interactions.interaction_matrix(
                    conversations
                ),

            "strongest_connections":
                self.interactions.strongest_connections(
                    conversations
                ),

            "attachments":
                self.attachments.summary(
                    messages
                ),

            "timeline":
                self.timeline.build(
                    messages
                ),

        }