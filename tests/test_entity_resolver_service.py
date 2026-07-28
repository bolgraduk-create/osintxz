"""
Tests for EntityResolverService.
"""

from unittest.mock import MagicMock


from app.services.entity_resolver_service import (
    EntityResolverService,
)



def test_service_creation():

    session = MagicMock()


    service = EntityResolverService(
        session
    )


    assert (
        service.session
        ==
        session
    )