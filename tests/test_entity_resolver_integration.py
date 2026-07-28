"""
Integration tests for EntityResolverService.
"""

from unittest.mock import MagicMock
from uuid import uuid4

from app.models.entity import EntityType

from app.services.entity_resolver_service import (
    EntityResolverService,
)


class FakeEntity:
    """
    Lightweight entity object.

    Used to test resolver logic
    without initializing SQLAlchemy models.
    """

    def __init__(
        self,
        value: str,
        entity_type: EntityType,
    ):
        self.id = uuid4()
        self.value = value
        self.entity_type = entity_type



def create_entity(
    value: str,
    entity_type: EntityType,
):
    return FakeEntity(
        value,
        entity_type,
    )



def test_same_email():

    session = MagicMock()

    service = EntityResolverService(
        session
    )

    first = create_entity(
        "John@Mail.com",
        EntityType.EMAIL,
    )

    second = create_entity(
        "john@mail.com",
        EntityType.EMAIL,
    )

    assert service.are_same_entity(
        first,
        second,
    )



def test_different_email():

    session = MagicMock()

    service = EntityResolverService(
        session
    )

    first = create_entity(
        "a@mail.com",
        EntityType.EMAIL,
    )

    second = create_entity(
        "b@mail.com",
        EntityType.EMAIL,
    )

    assert not service.are_same_entity(
        first,
        second,
    )



def test_different_entity_types():

    session = MagicMock()

    service = EntityResolverService(
        session
    )

    first = create_entity(
        "123456",
        EntityType.PHONE,
    )

    second = create_entity(
        "123456",
        EntityType.EMAIL,
    )

    assert not service.are_same_entity(
        first,
        second,
    )