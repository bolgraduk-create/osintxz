"""
Full entity resolution flow tests.
"""

from unittest.mock import MagicMock, patch

from uuid import uuid4

from app.models.entity import EntityType

from app.services.entity_resolution_pipeline import (
    EntityResolutionPipeline,
)



class FakeEntity:

    def __init__(
        self,
        value,
        entity_type,
    ):
        self.id = uuid4()
        self.value = value
        self.entity_type = entity_type



def test_pipeline_calls_resolver():

    session = MagicMock()


    pipeline = EntityResolutionPipeline(
        session
    )


    first = FakeEntity(
        "test@mail.com",
        EntityType.EMAIL,
    )


    second = FakeEntity(
        "test@mail.com",
        EntityType.EMAIL,
    )


    with patch.object(
        pipeline.resolver,
        "resolve",
    ) as resolver_mock:


        pipeline.process_pair(
            first,
            second,
        )


        resolver_mock.assert_called_once_with(
            first,
            second,
        )