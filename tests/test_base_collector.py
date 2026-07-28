"""
Tests for BaseCollector.
"""


import pytest


from app.collection.base import (
    BaseCollector,
)



def test_base_collector_requires_implementation():

    with pytest.raises(
        TypeError
    ):

        BaseCollector()



def test_collector_metadata():

    class TestCollector(
        BaseCollector
    ):

        def collect(
            self,
            source,
        ):

            return source



    collector = TestCollector()


    metadata = (
        collector.metadata()
    )


    assert (
        metadata["type"]
        ==
        "TestCollector"
    )