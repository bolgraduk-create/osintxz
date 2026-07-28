"""
Suspicious graph pattern detector.
"""

from __future__ import annotations

from uuid import UUID

from app.models.entity_graph import (
    EntityGraph,
)



class PatternDetector:
    """
    Detects suspicious structures
    inside entity graphs.
    """


    def __init__(
        self,
        graph: EntityGraph,
    ):
        self.graph = graph



    def find_high_degree_nodes(
        self,
        threshold: int = 3,
    ) -> list[UUID]:
        """
        Find entities with many connections.
        """

        result = []


        for node_id in self.graph.nodes:

            connections = len(
                self.graph.get_neighbors(
                    node_id
                )
            )


            if connections >= threshold:

                result.append(
                    node_id
                )


        return result



    def find_shared_connections(
        self,
    ) -> list[tuple[UUID, int]]:
        """
        Find nodes connected
        to many entities.
        """

        result = []


        for node_id in self.graph.nodes:

            count = len(
                self.graph.get_neighbors(
                    node_id
                )
            )


            result.append(
                (
                    node_id,
                    count,
                )
            )


        return sorted(
            result,
            key=lambda item: item[1],
            reverse=True,
        )