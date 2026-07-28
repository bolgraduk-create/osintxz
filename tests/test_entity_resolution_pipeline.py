"""
Tests for EntityResolutionPipeline.
"""

from unittest.mock import MagicMock


from app.services.entity_resolution_pipeline import (
    EntityResolutionPipeline,
)



def test_pipeline_creation():

    session = MagicMock()


    pipeline = EntityResolutionPipeline(
        session
    )


    assert (
        pipeline.session
        ==
        session
    )