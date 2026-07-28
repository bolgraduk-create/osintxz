"""
Telegram interaction service.

Builds interaction statistics between participants.

Responsibilities:

- count replies
- count co-occurrence
- calculate interaction strength

Does NOT:

- build relationship graph
- create entities
- AI analysis
"""

from __future__ import annotations

from collections import Counter


class TelegramInteractionService:
    """
    Telegram interaction analysis.
    """

    def interaction_matrix(
        self,
        conversations,
    ) -> dict[tuple[str, str], int]:
        """
        Count participant interactions inside conversations.
        """

        counter = Counter()

        for conversation in conversations:

            participants = []

            for message in conversation:

                sender = getattr(
                    message,
                    "sender",
                    None,
                )

                if sender:
                    participants.append(sender)

            participants = list(
                dict.fromkeys(
                    participants
                )
            )

            for i in range(
                len(participants)
            ):

                for j in range(
                    i + 1,
                    len(participants)
                ):

                    pair = tuple(
                        sorted(
                            (
                                participants[i],
                                participants[j],
                            )
                        )
                    )

                    counter[pair] += 1

        return dict(counter)

    def strongest_connections(
        self,
        conversations,
        limit: int = 20,
    ) -> list[tuple[tuple[str, str], int]]:
        """
        Return strongest participant connections.
        """

        matrix = self.interaction_matrix(
            conversations
        )

        return sorted(
            matrix.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]