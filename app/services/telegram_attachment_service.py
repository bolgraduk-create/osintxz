"""
Telegram attachment service.

Analyzes media contained in Telegram exports.

Responsibilities:

- count media types
- collect attachment statistics
- prepare attachment summary

Does NOT:

- OCR
- image recognition
- AI analysis
"""

from __future__ import annotations

from collections import Counter


class TelegramAttachmentService:
    """
    Telegram attachment statistics.
    """

    def media_statistics(
        self,
        messages,
    ) -> dict[str, int]:
        """
        Count attachment types.
        """

        counter = Counter()

        for message in messages:

            media_type = getattr(
                message,
                "media_type",
                None,
            )

            if media_type:

                counter[
                    str(media_type)
                ] += 1

        return dict(counter)

    def attachment_count(
        self,
        messages,
    ) -> int:
        """
        Count messages with attachments.
        """

        total = 0

        for message in messages:

            if getattr(
                message,
                "media_type",
                None,
            ):
                total += 1

        return total

    def attachment_ratio(
        self,
        messages,
    ) -> float:
        """
        Percentage of messages containing media.
        """

        if not messages:
            return 0.0

        return (
            self.attachment_count(messages)
            / len(messages)
        )

    def summary(
        self,
        messages,
    ) -> dict:
        """
        Build media summary.
        """

        return {

            "attachments": self.attachment_count(
                messages,
            ),

            "ratio": self.attachment_ratio(
                messages,
            ),

            "media_types": self.media_statistics(
                messages,
            ),

        }