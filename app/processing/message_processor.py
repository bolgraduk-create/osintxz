"""
Message processor.

Normalizes imported messages
from different sources.

Supported sources:

- Telegram
- WhatsApp
- Discord
- Email

Specific importers will convert
their data into this processor format.
"""

from __future__ import annotations

from datetime import datetime

from typing import Any

from app.processing.base_processor import (
    BaseProcessor,
)


class MessageProcessor(
    BaseProcessor,
):
    """
    Processes message data.
    """


    def process(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize message data.

        Expected input:

        {
            sender,
            text,
            date,
            receiver,
            chat_name
        }

        Returns data compatible
        with Message model.
        """


        return {
            "sender": data.get(
                "sender"
            ),

            "receiver": data.get(
                "receiver"
            ),

            "chat_name": data.get(
                "chat_name"
            ),

            "text": data.get(
                "text"
            ),

            "sent_at": self._parse_date(
                data.get("date")
            ),

            "external_id": data.get(
                "external_id"
            ),

            "metadata_json": data.get(
                "metadata_json"
            ),
        }


    def _parse_date(
        self,
        value: Any,
    ) -> datetime | None:
        """
        Convert incoming date
        into datetime object.
        """


        if value is None:
            return None


        if isinstance(
            value,
            datetime,
        ):
            return value


        if isinstance(
            value,
            str,
        ):

            try:
                return datetime.fromisoformat(
                    value
                )

            except ValueError:
                return None


        return None