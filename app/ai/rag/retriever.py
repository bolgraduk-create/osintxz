"""
Knowledge Retriever.

Retrieves relevant information from
KnowledgeStore.

Version:
v1.1

Features:
- keyword search
- text normalization
- relevance scoring
"""

from __future__ import annotations

import re

from typing import Any


from app.ai.rag.knowledge_store import (
    KnowledgeStore,
)



class Retriever:
    """
    Retrieval layer for RAG.
    """


    def __init__(
        self,
        knowledge_store: KnowledgeStore,
    ):
        self.knowledge_store = (
            knowledge_store
        )


    # ==========================================================
    # Main retrieval
    # ==========================================================

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant knowledge.
        """

        results = self.retrieve_by_keywords(query)
        ranked = results

        return self.limit_results(
            ranked,
            limit,
        )


    # ==========================================================
    # Keyword retrieval
    # ==========================================================

    def retrieve_by_keywords(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
       """
       Retrieve from knowledge store.
       """

       return (
           self.knowledge_store.search(
               query
            )
        )


    # ==========================================================
    # Text processing
    # ==========================================================

    def normalize_text(
        self,
        text: str,
    ) -> list[str]:
        """
        Normalize text into tokens.
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
    # Ranking
    # ==========================================================

    def rank_results(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Rank results by keyword overlap.
        """


        query_words = set(
            self.normalize_text(
                query
            )
        )


        scored = []


        for item in results:

            content_words = set(
                self.normalize_text(
                    item.get(
                        "content",
                        "",
                    )
                )
            )


            score = len(
                query_words.intersection(
                    content_words
                )
            )


            scored.append(
                (
                    score,
                    item,
                )
            )


        scored.sort(
            key=lambda x: x[0],
            reverse=True,
        )


        return [
            item
            for score, item in scored
            if score > 0
        ]


    # ==========================================================
    # Limit
    # ==========================================================

    def limit_results(
        self,
        results: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Limit result count.
        """

        return results[:limit]


    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Retriever metadata.
        """

        return {

            "type":
                "keyword_retriever",

            "version":
                "1.1",

            "storage":
                self.knowledge_store.metadata(),

        }