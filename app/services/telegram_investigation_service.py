"""
Telegram investigation service.

Integrates Telegram intelligence with investigation.

Responsibilities:

- run Telegram analysis
- convert analysis into investigation artifacts
- prepare investigation context

Does NOT:

- import Telegram exports
- run AI analysis
- save database objects
"""

from __future__ import annotations

from app.services.telegram_analysis_service import (
    TelegramAnalysisService,
)


class TelegramInvestigationService:
    """
    Telegram investigation integration.
    """

    def __init__(
        self,
        analysis_service: TelegramAnalysisService,
    ):
        self.analysis_service = (
            analysis_service
        )

    def analyze(
        self,
        messages,
    ) -> dict:
        """
        Build Telegram investigation.
        """

        analysis = (
            self.analysis_service.analyze(
                messages
            )
        )

        return {

            "statistics":
                analysis["statistics"],

            "keywords":
                analysis["keywords"],

            "timeline":
                analysis["timeline"],

            "attachments":
                analysis["attachments"],

            "connections":
                analysis[
                    "strongest_connections"
                ],

            "activity": {

                "day":
                    analysis[
                        "activity_by_day"
                    ],

                "hour":
                    analysis[
                        "activity_by_hour"
                    ],

                "weekday":
                    analysis[
                        "activity_by_weekday"
                    ],

            },

            "conversation_count":
                analysis[
                    "conversation_count"
                ],

        }