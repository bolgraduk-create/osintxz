"""
Tests for BaseExporter interface.
"""


import pytest


from app.exporters.base import (
    BaseExporter,
)



def test_base_exporter_is_abstract():

    with pytest.raises(
        TypeError
    ):

        BaseExporter()