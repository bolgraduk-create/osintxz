"""
Connection analyzer.

Provides graph connection analysis
for investigation entities.
"""

from __future__ import annotations


from collections import deque

from uuid import UUID


from app.models.entity_graph import (
    EntityGraph,
)



class ConnectionAnalyzer:
    """
    Analyzer for entity graph connections.
    """


    def __init__(
        self,
        graph: EntityGraph,
    ):
        self.graph = graph



    def get_connections(
        self,
        entity_id: UUID,
    ) -> list[UUID]:
        """
        Return direct connections
        of an entity.
        """

        return self.graph.get_neighbors(
            entity_id
        )



    def has_connection(
        self,
        source_id: UUID,
        target_id: UUID,
    ) -> bool:
        """
        Check direct connection
        between entities.
        """

        return (
            target_id
            in self.graph.get_neighbors(
                source_id
            )
        )



    def count_connections(
        self,
        entity_id: UUID,
    ) -> int:
        """
        Return number of direct connections.
        """

        return len(
            self.graph.get_neighbors(
                entity_id
            )
        )



    def find_path(
        self,
        start_id: UUID,
        end_id: UUID,
    ) -> list[UUID] | None:
        """
        Find shortest path between entities.

        Uses breadth-first search.
        """

        queue = deque(
            [
                (
                    start_id,
                    [start_id],
                )
            ]
        )


        visited = {
            start_id
        }


        while queue:

            current, path = queue.popleft()


            if current == end_id:
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


    def get_connection_strength(
        self,
        source_id: UUID,
        target_id: UUID,
    ) -> float:
        """
        Return strongest direct connection
        confidence between two entities.
        """

        strengths: list[float] = []

        for edge in self.graph.edges:
            if (
                edge.source_id == source_id
                and edge.target_id == target_id
            ) or (
                edge.source_id == target_id
                and edge.target_id == source_id
            ):
                strengths.append(edge.confidence)

        if not strengths:
            return 0.0

        return max(strengths)
        return None