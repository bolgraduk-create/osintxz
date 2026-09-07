"""
Integration tests for the modern case-scoped EntityResolverService.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.entity import EntityType
from app.services.entity_resolver_service import EntityResolverService


class FakeEntity:
    """Minimal modern entity contract used without SQLAlchemy setup."""

    def __init__(
        self,
        value: str,
        entity_type: EntityType,
        *,
        case_id,
    ) -> None:
        self.id = uuid4()
        self.case_id = case_id
        self.value = value
        self.entity_type = entity_type
        self.normalized_value = None
        self.metadata_json = None


def create_entity(
    value: str,
    entity_type: EntityType,
    *,
    case_id,
) -> FakeEntity:
    return FakeEntity(
        value,
        entity_type,
        case_id=case_id,
    )


def test_same_email():
    session = MagicMock()
    service = EntityResolverService(session)
    case_id = uuid4()

    first = create_entity(
        "John@Mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )
    second = create_entity(
        "john@mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )

    assert service.are_same_entity(
        first,
        second,
    )


def test_different_email():
    session = MagicMock()
    service = EntityResolverService(session)
    case_id = uuid4()

    first = create_entity(
        "a@mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )
    second = create_entity(
        "b@mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )

    assert not service.are_same_entity(
        first,
        second,
    )


def test_different_entity_types_are_rejected_as_invalid_candidate():
    """Cross-type pairs are not valid modern resolution candidates."""

    session = MagicMock()
    service = EntityResolverService(session)
    case_id = uuid4()

    first = create_entity(
        "123456",
        EntityType.PHONE,
        case_id=case_id,
    )
    second = create_entity(
        "123456",
        EntityType.EMAIL,
        case_id=case_id,
    )

    with pytest.raises(
        ValueError,
        match="same entity type",
    ):
        service.are_same_entity(
            first,
            second,
        )
