"""
Entity graph service.

Responsible for:

- building investigation entity graphs
- preparing graph data for application and UI layers
- calculating basic graph statistics

Does NOT:

- access UI components
- execute SQL directly
- persist graph snapshots
- modify entities or relationships
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entity_graph import (
    EntityGraph,
)

from app.repositories.entity_graph_repository import (
    EntityGraphRepository,
)


class EntityGraphService:
    """
    Service for investigation entity graphs.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.repository = EntityGraphRepository(
            session
        )

    # ==========================================================
    # Graph
    # ==========================================================

    def get_case_graph(
        self,
        case_id: UUID,
    ) -> EntityGraph:
        """
        Build and return the domain graph for a case.
        """

        return self.repository.build_case_graph(
            case_id
        )

    def get_case_graph_data(
        self,
        case_id: UUID,
    ) -> dict[str, Any]:
        """
        Build graph and return UI-ready data.
        """

        graph = self.get_case_graph(
            case_id
        )

        degrees = self._calculate_degrees(
            graph
        )

        nodes = []

        for entity_id, node in graph.nodes.items():

            degree = degrees.get(
                entity_id,
                0,
            )

            nodes.append(
                {
                    "id": str(
                        node.entity_id
                    ),
                    "label": node.label,
                    "type": node.entity_type,
                    "degree": degree,
                    "is_isolated": (
                        degree == 0
                    ),
                }
            )

        edges = []

        for index, edge in enumerate(
            graph.edges
        ):

            edges.append(
                {
                    "id": (
                        f"{edge.source_id}:"
                        f"{edge.target_id}:"
                        f"{index}"
                    ),
                    "source": str(
                        edge.source_id
                    ),
                    "target": str(
                        edge.target_id
                    ),
                    "type": (
                        edge.relationship_type
                    ),
                    "confidence": (
                        edge.confidence
                    ),
                }
            )

        nodes.sort(
            key=lambda item: (
                -item["degree"],
                item["label"].lower(),
            )
        )

        edges.sort(
            key=lambda item: (
                item["source"],
                item["target"],
                item["type"],
            )
        )

        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": (
                self._build_statistics(
                    graph=graph,
                    degrees=degrees,
                )
            ),
        }

    # ==========================================================
    # Statistics
    # ==========================================================

    def _build_statistics(
        self,
        graph: EntityGraph,
        degrees: dict[UUID, int],
    ) -> dict[str, Any]:
        """
        Calculate basic graph statistics.
        """

        node_count = len(
            graph.nodes
        )

        edge_count = len(
            graph.edges
        )

        isolated_nodes = sum(
            1
            for degree in degrees.values()
            if degree == 0
        )

        connected_nodes = (
            node_count - isolated_nodes
        )

        maximum_degree = max(
            degrees.values(),
            default=0,
        )

        average_degree = (
            sum(
                degrees.values()
            )
            / node_count
            if node_count > 0
            else 0.0
        )

        density = self._calculate_density(
            node_count=node_count,
            edge_count=edge_count,
        )

        type_counts: dict[str, int] = {}

        for node in graph.nodes.values():

            type_counts[
                node.entity_type
            ] = (
                type_counts.get(
                    node.entity_type,
                    0,
                )
                + 1
            )

        relationship_type_counts: (
            dict[str, int]
        ) = {}

        for edge in graph.edges:

            relationship_type_counts[
                edge.relationship_type
            ] = (
                relationship_type_counts.get(
                    edge.relationship_type,
                    0,
                )
                + 1
            )

        return {
            "nodes": node_count,
            "edges": edge_count,
            "connected_nodes": (
                connected_nodes
            ),
            "isolated_nodes": (
                isolated_nodes
            ),
            "maximum_degree": (
                maximum_degree
            ),
            "average_degree": round(
                average_degree,
                4,
            ),
            "density": round(
                density,
                6,
            ),
            "entity_types": dict(
                sorted(
                    type_counts.items()
                )
            ),
            "relationship_types": dict(
                sorted(
                    relationship_type_counts.items()
                )
            ),
        }

    def _calculate_degrees(
        self,
        graph: EntityGraph,
    ) -> dict[UUID, int]:
        """
        Calculate undirected node degree.
        """

        degrees = {
            entity_id: 0
            for entity_id in graph.nodes
        }

        for edge in graph.edges:

            if edge.source_id in degrees:

                degrees[
                    edge.source_id
                ] += 1

            if edge.target_id in degrees:

                degrees[
                    edge.target_id
                ] += 1

        return degrees

    def _calculate_density(
        self,
        node_count: int,
        edge_count: int,
    ) -> float:
        """
        Calculate undirected graph density.

        Multiple relationships between the same
        entities are counted as separate edges.
        """

        if node_count < 2:
            return 0.0

        maximum_edges = (
            node_count
            * (
                node_count - 1
            )
            / 2
        )

        return (
            edge_count
            / maximum_edges
        )