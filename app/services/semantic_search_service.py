"""
Semantic search service.

Provides similarity based
search over indexed objects.
"""

from __future__ import annotations

from uuid import UUID

from app.models.search_index import SearchIndex



class SemanticSearchService:
    """
    Semantic search engine.
    """



    def cosine_similarity(
        self,
        vector_a: list[float],
        vector_b: list[float],
    ) -> float:
        """
        Calculate cosine similarity.
        """

        if not vector_a or not vector_b:
            return 0.0


        dot = sum(
            a * b
            for a, b in zip(
                vector_a,
                vector_b,
            )
        )


        norm_a = sum(
            a * a
            for a in vector_a
        ) ** 0.5


        norm_b = sum(
            b * b
            for b in vector_b
        ) ** 0.5


        if norm_a == 0 or norm_b == 0:
            return 0.0


        return dot / (
            norm_a * norm_b
        )



    def rank_by_similarity(
        self,
        items: list[tuple[SearchIndex, float]],
    ) -> list[SearchIndex]:
        """
        Sort objects by similarity.
        """

        ranked = sorted(
            items,
            key=lambda item: item[1],
            reverse=True,
        )


        return [
            item[0]
            for item in ranked
        ]