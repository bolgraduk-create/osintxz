"""
Telegram keyword service.

Extracts the most frequent words from Telegram messages.

Responsibilities:

- normalize text
- count word frequency
- ignore stop words

Does NOT:

- AI analysis
- entity extraction
- relationship detection
"""

from __future__ import annotations

import re
from collections import Counter


STOP_WORDS = {
    "",
    "и",
    "в",
    "во",
    "на",
    "не",
    "что",
    "это",
    "как",
    "к",
    "по",
    "за",
    "от",
    "до",
    "из",
    "для",
    "а",
    "но",
    "или",
    "the",
    "is",
    "are",
    "of",
    "to",
    "and",
    "in",
}


class TelegramKeywordService:
    """
    Telegram keyword extraction.
    """

    WORD_PATTERN = re.compile(
        r"[A-Za-zА-Яа-яЁёЇїІіЄєҐґ0-9_]+"
    )

    def tokenize(
        self,
        text: str,
    ) -> list[str]:

        words = self.WORD_PATTERN.findall(
            text.lower()
        )

        return [
            word
            for word in words
            if word not in STOP_WORDS
            and len(word) > 2
        ]

    def extract(
        self,
        messages,
        limit: int = 50,
    ) -> list[tuple[str, int]]:

        counter = Counter()

        for message in messages:

            text = getattr(
                message,
                "text",
                "",
            )

            if not text:
                continue

            counter.update(
                self.tokenize(text)
            )

        return counter.most_common(limit)