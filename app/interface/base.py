"""
Base interface definition.

Provides common contract
for user interfaces.

Does NOT contain
application logic.
"""

from __future__ import annotations


from abc import ABC, abstractmethod


from typing import Any



class BaseInterface(
    ABC
):
    """
    Abstract interface contract.
    """



    @abstractmethod
    def handle(
        self,
        request: Any,
    ) -> Any:
        """
        Handle incoming request.
        """

        raise NotImplementedError