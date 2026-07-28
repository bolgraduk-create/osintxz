"""
Telegram entity mapper service.

Converts Telegram intelligence into investigation entities.

Responsibilities:

- map Telegram participants
- prepare entity payloads
- normalize values

Does NOT:

- save entities
- create relationships
- perform AI analysis
"""

from __future__ import annotations


class TelegramEntityMapperService:
    """
    Maps Telegram analysis into investigation entities.
    """

    def participants_to_entities(
        self,
        messages,
    ) -> list[dict]:
        """
        Convert Telegram participants into entity payloads.
        """

        participants = {}

        for message in messages:

            sender = getattr(
                message,
                "sender",
                None,
            )

            if not sender:
                continue

            if sender not in participants:

                participants[sender] = {

                    "type": "person",

                    "value": sender,

                    "metadata": {
                        "source": "telegram",
                    },

                }

        return list(
            participants.values()
        )