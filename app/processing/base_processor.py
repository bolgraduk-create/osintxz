"""
Base processor.

All data processors must inherit
from this class.

Processors transform external data
into application domain objects.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from typing import Any


class BaseProcessor(
    ABC,
):
    """
    Abstract base processor.
    """


    @abstractmethod
    def process(
        self,
        data: Any,
    ) -> Any:
        """
        Process incoming data.

        Every processor must implement
        this method.
        """

        raise NotImplementedError