"""
Tests for EntityMergeRepository.
"""

from unittest.mock import MagicMock


from app.repositories.entity_merge_repository import (
    EntityMergeRepository,
)


def test_repository_creation():

    session = MagicMock()


    repository = EntityMergeRepository(
        session
    )


    assert (
        repository.session
        ==
        session
    )