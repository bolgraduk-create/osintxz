"""
Knowledge Store.

Stores and retrieves knowledge
for RAG pipeline.

Responsibilities:

- store knowledge items
- search knowledge
- provide metadata

Does NOT:

- generate answers
- rank results
- call AI models
"""

from __future__ import annotations

from datetime import datetime, timezone

import re

from typing import Any


class KnowledgeStore:
    """
    In-memory knowledge storage.

    Later can be replaced by:
    - database storage
    - vector database
    - embedding storage
    """


    def __init__(
        self,
    ):
        self._knowledge: list[
            dict[str, Any]
        ] = []


    # ==========================================================
    # Add knowledge
    # ==========================================================

    def add(
        self,
        key: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Add knowledge item.
        """


        item = {

            "key":
                key,

            "content":
                content,

            "metadata":
                metadata or {},

            "created_at":
                datetime.now(
                    timezone.utc
                ),

        }


        self._knowledge.append(
            item
        )


        return item


    # ==========================================================
    # Search
    # ==========================================================

    def search(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge.

        Uses keyword matching.
        """


        query_words = (
            self._normalize_text(
                query
            )
        )


        if not query_words:
            return []


        results = []


        for item in self._knowledge:

            content_words = (
                self._normalize_text(
                    item.get(
                        "content",
                        "",
                    )
                )
            )


            matches = (
                set(query_words)
                &
                set(content_words)
            )


            if matches:

                results.append(
                    item
                )


        return results


    # ==========================================================
    # Helpers
    # ==========================================================

    def _normalize_text(
        self,
        text: str,
    ) -> list[str]:
        """
        Normalize text.

        Removes punctuation
        and lowercases.
        """


        text = (
            text.lower()
        )


        text = re.sub(
            r"[^a-zа-я0-9\s]",
            " ",
            text,
        )


        return [
            word
            for word in text.split()
            if word
        ]


    # ==========================================================
    # Get all
    # ==========================================================

    def all(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all knowledge.
        """

        return list(
            self._knowledge
        )


    # ==========================================================
    # Clear
    # ==========================================================

    def clear(
        self,
    ):
        """
        Remove all knowledge.
        """

        self._knowledge.clear()


    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Store metadata.
        """

        return {

            "type":
                "knowledge_store",

            "items":
                len(
                    self._knowledge
                ),

        }