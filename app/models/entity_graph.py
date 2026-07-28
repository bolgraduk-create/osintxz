"""
Entity graph model.

Represents analytical graph
built from investigation entities
and relationships.
"""

from __future__ import annotations

from uuid import UUID

from dataclasses import dataclass, field



@dataclass
class GraphNode:
    """
    Graph node representing entity.
    """

    entity_id: UUID

    label: str

    entity_type: str



@dataclass
class GraphEdge:
    """
    Graph edge representing relationship.
    """

    source_id: UUID

    target_id: UUID

    relationship_type: str

    confidence: float = 1.0



@dataclass
class EntityGraph:
    """
    Analytical entity graph.
    """

    nodes: dict[UUID, GraphNode] = field(
        default_factory=dict
    )

    edges: list[GraphEdge] = field(
        default_factory=list
    )


    def add_node(
        self,
        node: GraphNode,
    ) -> None:
        """
        Add graph node.
        """

        self.nodes[node.entity_id] = node



    def add_edge(
        self,
        edge: GraphEdge,
    ) -> None:
        """
        Add graph edge.
        """

        self.edges.append(
            edge
        )



    def get_neighbors(
        self,
        entity_id: UUID,
    ) -> list[UUID]:
        """
        Return connected entities.
        """

        neighbors = []


        for edge in self.edges:

            if edge.source_id == entity_id:
                neighbors.append(
                    edge.target_id
                )

            elif edge.target_id == entity_id:
                neighbors.append(
                    edge.source_id
                )


        return neighbors