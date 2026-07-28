"""
Telegram intelligence service.

Builds intelligence from Telegram investigation.

Responsibilities:

- analyze Telegram messages
- calculate participant activity
- detect top participants
- build statistics

Does NOT:

- import Telegram exports
- build relationships
- generate AI reports
"""

from __future__ import annotations

from collections import Counter


class TelegramIntelligenceService:
    """
    Telegram investigation intelligence.
    """

    def participant_activity(
        self,
        messages,
    ) -> dict[str, int]:
        """
        Count messages per participant.
        """

        counter = Counter()

        for message in messages:

            sender = getattr(
                message,
                "sender",
                None,
            )

            if sender:
                counter[sender] += 1

        return dict(counter)

    def top_participants(
        self,
        messages,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        """
        Return most active participants.
        """

        activity = self.participant_activity(
            messages
        )

        return sorted(
            activity.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

    def message_count(
        self,
        messages,
    ) -> int:
        """
        Total message count.
        """

        return len(messages)

    def participant_count(
        self,
        messages,
    ) -> int:
        """
        Unique participant count.
        """

        activity = self.participant_activity(
            messages
        )

        return len(activity)

    def statistics(
        self,
        messages,
    ) -> dict:
        """
        Telegram statistics.
        """

        return {

            "messages": self.message_count(
                messages,
            ),

            "participants": self.participant_count(
                messages,
            ),

            "top_participants": self.top_participants(
                messages,
            ),

        }