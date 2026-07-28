"""
Universal collection pipeline.

Coordinates all collectors.

Responsibilities:

- choose collectors
- execute collection
- merge results
- continue on collector failures

Does NOT:

- analyze evidence
- save to database
- call AI
"""

from __future__ import annotations

from pathlib import Path

from app.collection.base import BaseCollector
from app.collection.manager import CollectionManager
from app.collection.models import CollectionResult


class CollectionPipeline:
    """
    Runs the complete collection process.
    """

    def __init__(
        self,
        manager: CollectionManager,
    ) -> None:

        self.manager = manager

    def collect(
        self,
        path: str | Path,
    ) -> list[CollectionResult]:
        """
        Execute every compatible collector.
        """

        return self.manager.collect(path)

    def collect_first(
        self,
        path: str | Path,
    ) -> CollectionResult | None:
        """
        Execute only the first compatible collector.
        """

        results = self.collect(path)

        if not results:
            return None

        return results[0]

    def register(
        self,
        collector: BaseCollector,
    ) -> None:
        """
        Register additional collector.
        """

        self.manager.register(collector)

    def clear(
        self,
    ) -> None:
        """
        Remove all collectors.
        """

        self.manager.clear()