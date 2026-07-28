"""
Telegram collector.

Collects data from Telegram Desktop exports.

Supported:

- result.json
"""

from __future__ import annotations


import json


from pathlib import Path


from typing import Any


from app.collection.base import (
    BaseCollector,
)


from app.collection.models import (
    CollectedData,
)



class TelegramCollector(
    BaseCollector
):
    """
    Collector for Telegram exports.
    """



    def collect(
        self,
        source: str | Path,
    ) -> CollectedData:
        """
        Load Telegram export.
        """

        path = Path(
            source
        )


        if not path.exists():

            raise FileNotFoundError(
                path
            )


        if path.suffix.lower() != ".json":

            raise ValueError(
                "Telegram export must be JSON"
            )


        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )



        messages = (
            data.get(
                "messages",
                []
            )
        )


        users = set()



        normalized_messages = []



        for message in messages:

            if not isinstance(
                message,
                dict
            ):
                continue



            sender = (
                message.get(
                    "from"
                )
            )


            if sender:

                users.add(
                    sender
                )



            normalized_messages.append(

                {

                    "from":
                        sender,


                    "text":
                        self._extract_text(
                            message
                        ),


                    "date":
                        message.get(
                            "date"
                        ),


                    "type":
                        message.get(
                            "type"
                        ),

                }

            )



        metadata = {

            "message_count":
                len(
                    normalized_messages
                ),


            "users":
                list(
                    users
                ),

        }



        return CollectedData(

            source="telegram",

            content=normalized_messages,

            metadata=metadata,

        )



    def _extract_text(
        self,
        message: dict[str, Any],
    ) -> str:

        text = (
            message.get(
                "text",
                ""
            )
        )


        if isinstance(
            text,
            str
        ):

            return text



        if isinstance(
            text,
            list
        ):

            parts = []


            for item in text:

                if isinstance(
                    item,
                    str
                ):

                    parts.append(
                        item
                    )


                elif isinstance(
                    item,
                    dict
                ):

                    parts.append(
                        str(
                            item.get(
                                "text",
                                ""
                            )
                        )
                    )


            return "".join(
                parts
            )



        return str(
            text
        )