"""
Entity graph repository.

Builds analytical graph
from database entities
and relationships.
"""

from __future__ import annotations


from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session


from app.models.entity import Entity
from app.models.relationship import Relationship


from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
    GraphEdge,
)



class EntityGraphRepository:
    """
    Repository for building entity graphs.
    """


    def __init__(
        self,
        session: Session,
    ):
        self.session = session



    def build_case_graph(
        self,
        case_id: UUID,
    ) -> EntityGraph:
        """
        Build graph for investigation case.
        """

        graph = EntityGraph()


        entities = self.session.execute(
            select(Entity)
            .where(
                Entity.case_id == case_id
            )
        )


        for entity in entities.scalars().all():

            graph.add_node(
                GraphNode(
                    entity_id=entity.id,
                    label=entity.value,
                    entity_type=entity.entity_type.value,
                )
            )


        relationships = self.session.execute(
            select(Relationship)
            .where(
                Relationship.case_id == case_id
            )
        )


        for relationship in relationships.scalars().all():

            graph.add_edge(
                GraphEdge(
                    source_id=relationship.source_entity_id,
                    target_id=relationship.target_entity_id,
                    relationship_type=(
                        relationship.relationship_type.value
                    ),
                    confidence=relationship.confidence,
                )
            )


        return graph