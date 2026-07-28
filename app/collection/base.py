"""
Base collector definition.

Provides common interface
for all data collectors.
"""

from __future__ import annotations


from abc import ABC, abstractmethod


from typing import Any



class BaseCollector(
    ABC
):
    """
    Abstract collector contract.
    """



    @abstractmethod
    def collect(
        self,
        source: Any,
    ):
        """
        Collect data from source.
        """

        raise NotImplementedError



    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Collector metadata.
        """

        return {

            "type":
                self.__class__.__name__,

        }