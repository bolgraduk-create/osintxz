"""
Tests for BaseInterface.
"""


import pytest


from app.interface.base import (
    BaseInterface,
)



def test_base_interface_requires_implementation():

    with pytest.raises(
        TypeError
    ):

        BaseInterface()