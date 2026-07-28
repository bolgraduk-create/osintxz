"""
Full text search service.

Provides normalized text search
over investigation indexes.
"""

from __future__ import annotations

from uuid import UUID

from app.models.search_index import (
    SearchIndex,
)



class FullTextSearchService:
    """
    Full text search engine.
    """



    def normalize(
        self,
        text: str,
    ) -> str:
        """
        Normalize text.
        """

        return (
            text
            .lower()
            .strip()
        )



    def match(
        self,
        index: SearchIndex,
        query: str,
    ) -> bool:
        """
        Check if index matches query.
        """

        normalized_query = (
            self.normalize(query)
        )


        title = self.normalize(
            index.title
        )


        content = self.normalize(
            index.content
        )


        return (
            normalized_query in title
            or
            normalized_query in content
        )



    def rank(
        self,
        indexes: list[SearchIndex],
        query: str,
    ) -> list[SearchIndex]:
        """
        Rank search results.
        """

        normalized_query = (
            self.normalize(query)
        )


        def score(
            item: SearchIndex,
        ):

            value = 0


            if normalized_query in self.normalize(
                item.title
            ):
                value += 2


            if normalized_query in self.normalize(
                item.content
            ):
                value += 1


            return value


        return sorted(
            indexes,
            key=score,
            reverse=True,
        )