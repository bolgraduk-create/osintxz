"""
Tests for EntityGraphRepository.
"""

from unittest.mock import MagicMock


from app.repositories.entity_graph_repository import (
    EntityGraphRepository,
)



def test_repository_creation():

    session = MagicMock()


    repository = EntityGraphRepository(
        session
    )


    assert (
        repository.session
        ==
        session
    )