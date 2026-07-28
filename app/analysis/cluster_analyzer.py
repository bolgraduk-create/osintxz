"""
Cluster analyzer.

Detects connected groups
inside entity graph.
"""

from __future__ import annotations

from uuid import UUID

from collections import deque


from app.models.entity_graph import (
    EntityGraph,
)



class ClusterAnalyzer:
    """
    Analyzer for graph clusters.
    """


    def __init__(
        self,
        graph: EntityGraph,
    ):
        self.graph = graph



    def find_clusters(
        self,
    ) -> list[set[UUID]]:
        """
        Find connected components
        inside graph.
        """

        visited = set()

        clusters = []


        for node_id in self.graph.nodes:

            if node_id in visited:
                continue


            cluster = self._bfs_cluster(
                node_id,
                visited,
            )


            clusters.append(
                cluster
            )


        return clusters

    def score_clusters(
        self,
    ) -> list[tuple[set[UUID], float]]:
        """
        Calculate importance score
        for every cluster.
        """

        clusters = self.find_clusters()

        scored = []

        for cluster in clusters:
            score = 0.0

            # cluster size influence
            score += len(cluster)

            # connection density
            edges = 0

            for edge in self.graph.edges:
                if (
                    edge.source_id in cluster
                    and edge.target_id in cluster
                ):
                    edges += 1

            score += edges * 0.5

            scored.append((cluster, score))

        return sorted(
            scored,
            key=lambda item: item[1],
            reverse=True,
        )



    def _bfs_cluster(
        self,
        start: UUID,
        visited: set[UUID],
    ) -> set[UUID]:
        """
        Breadth-first search cluster.
        """

        queue = deque(
            [start]
        )

        cluster = set()


        visited.add(
            start
        )


        while queue:

            current = queue.popleft()


            cluster.add(
                current
            )


            for neighbor in self.graph.get_neighbors(
                current
            ):

                if neighbor not in visited:

                    visited.add(
                        neighbor
                    )

                    queue.append(
                        neighbor
                    )


        return cluster