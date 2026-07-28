"""
Centrality analyzer.

Provides graph importance analysis
for investigation entities.
"""

from __future__ import annotations

from uuid import UUID

from app.models.entity_graph import (
    EntityGraph,
)


class CentralityAnalyzer:
    """
    Analyzer for entity importance
    inside investigation graph.
    """

    def __init__(
        self,
        graph: EntityGraph,
    ):
        self.graph = graph


    def degree_centrality(
        self,
    ) -> dict[UUID, int]:
        """
        Calculate degree centrality.

        Counts number of connections
        for every node.
        """

        result = {}

        for node_id in self.graph.nodes:
            result[node_id] = len(
                self.graph.get_neighbors(
                    node_id
                )
            )

        return result



    def get_most_connected(
        self,
        limit: int = 5,
    ) -> list[tuple[UUID, int]]:
        """
        Return entities with most connections.
        """

        centrality = self.degree_centrality()

        return sorted(
            centrality.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]


    def betweenness_centrality(
        self,
    ) -> dict[UUID, float]:
        """
        Estimate betweenness centrality.

        Measures how often a node appears
        on shortest paths between nodes.
        """

        scores = {
            node_id: 0.0
            for node_id in self.graph.nodes
        }


        nodes = list(
            self.graph.nodes.keys()
        )


        for source in nodes:

            for target in nodes:

                if source == target:
                    continue


                path = self._find_path(
                    source,
                    target,
                )


                if not path:
                    continue


                for node in path[1:-1]:

                    scores[node] += 1.0


        return scores

    def rank_entities(
        self,
        limit: int = 10,
    ) -> list[tuple[UUID, float]]:
        """
        Rank entities by combined centrality.

        Combines:
        - degree centrality
        - betweenness centrality
        """

        degree = self.degree_centrality()

        between = self.betweenness_centrality()


        scores = {}


        for node_id in self.graph.nodes:

            scores[node_id] = (
                degree.get(
                    node_id,
                    0,
                )
                +
                between.get(
                    node_id,
                    0.0,
                )
            )


        return sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]



    def _find_path(
        self,
        start: UUID,
        end: UUID,
    ) -> list[UUID] | None:
        """
        Internal BFS path search.
        """

        from collections import deque


        queue = deque(
            [
                (
                    start,
                    [start],
                )
            ]
        )


        visited = {
            start
        }


        while queue:

            current, path = queue.popleft()


            if current == end:
                return path


            for neighbor in self.graph.get_neighbors(
                current
            ):

                if neighbor not in visited:

                    visited.add(
                        neighbor
                    )

                    queue.append(
                        (
                            neighbor,
                            path + [neighbor],
                        )
                    )


        return None