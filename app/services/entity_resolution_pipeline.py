"""
Entity resolution pipeline.

Coordinates entity resolution workflow.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entity import Entity

from app.services.entity_resolver_service import (
    EntityResolverService,
)



class EntityResolutionPipeline:
    """
    High-level entity resolution workflow.
    """


    def __init__(
        self,
        session: Session,
    ):
        self.session = session

        self.resolver = EntityResolverService(
            session
        )


    def process_pair(
        self,
        first: Entity,
        second: Entity,
    ):
        """
        Resolve pair of entities.
        """

        return self.resolver.resolve(
            first,
            second,
        )