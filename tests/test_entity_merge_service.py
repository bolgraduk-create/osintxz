"""
Tests for EntityMergeService.
"""

from unittest.mock import MagicMock

import pytest


from app.services.entity_merge_service import (
    EntityMergeService,
)


def test_service_creation():

    session = MagicMock()

    service = EntityMergeService(
        session
    )

    assert (
        service.session
        ==
        session
    )



def test_merge_same_entity_error():

    session = MagicMock()

    service = EntityMergeService(
        session
    )


    entity = MagicMock()

    entity.id = "same"


    with pytest.raises(
        ValueError
    ):
        service.merge_entities(
            entity,
            entity,
        )