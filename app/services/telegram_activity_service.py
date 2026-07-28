"""
Telegram activity service.

Builds activity statistics over time.

Responsibilities:

- activity by day
- activity by hour
- activity by weekday

Does NOT:

- build timeline
- AI analysis
- relationship analysis
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime


class TelegramActivityService:
    """
    Telegram activity statistics.
    """

    def activity_by_day(
        self,
        messages,
    ) -> dict[str, int]:

        counter = Counter()

        for message in messages:

            dt = getattr(
                message,
                "date",
                None,
            )

            if not isinstance(
                dt,
                datetime,
            ):
                continue

            counter[
                dt.strftime("%Y-%m-%d")
            ] += 1

        return dict(counter)

    def activity_by_hour(
        self,
        messages,
    ) -> dict[int, int]:

        counter = Counter()

        for message in messages:

            dt = getattr(
                message,
                "date",
                None,
            )

            if not isinstance(
                dt,
                datetime,
            ):
                continue

            counter[
                dt.hour
            ] += 1

        return dict(counter)

    def activity_by_weekday(
        self,
        messages,
    ) -> dict[str, int]:

        counter = Counter()

        for message in messages:

            dt = getattr(
                message,
                "date",
                None,
            )

            if not isinstance(
                dt,
                datetime,
            ):
                continue

            counter[
                dt.strftime("%A")
            ] += 1

        return dict(counter)