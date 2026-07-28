"""
Telegram conversation service.

Builds conversation blocks from Telegram messages.

Responsibilities:

- group consecutive messages
- split conversations by inactivity
- prepare conversation objects

Does NOT:

- AI analysis
- relationship analysis
- entity extraction
"""

from __future__ import annotations

from datetime import timedelta


class TelegramConversationService:
    """
    Detect Telegram conversations.
    """

    def build(
        self,
        messages,
        timeout_minutes: int = 30,
    ) -> list[list]:

        if not messages:
            return []

        timeout = timedelta(
            minutes=timeout_minutes,
        )

        conversations = []

        current = [
            messages[0]
        ]

        previous_date = getattr(
            messages[0],
            "date",
            None,
        )

        for message in messages[1:]:

            current_date = getattr(
                message,
                "date",
                None,
            )

            if (
                previous_date is None
                or
                current_date is None
            ):
                current.append(
                    message
                )
                previous_date = current_date
                continue

            if (
                current_date
                - previous_date
            ) > timeout:

                conversations.append(
                    current
                )

                current = [
                    message
                ]

            else:

                current.append(
                    message
                )

            previous_date = current_date

        if current:
            conversations.append(
                current
            )

        return conversations

    def sizes(
        self,
        conversations,
    ) -> list[int]:

        return [
            len(conversation)
            for conversation
            in conversations
        ]

    def largest(
        self,
        conversations,
    ):

        if not conversations:
            return None

        return max(
            conversations,
            key=len,
        )