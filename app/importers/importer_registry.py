"""
Importer registry.

Stores available importers and
selects the correct one for a source.
"""

from __future__ import annotations

from pathlib import Path

from app.importers.base_importer import BaseImporter


class ImporterRegistry:
    """
    Registry of available importers.
    """

    def __init__(self) -> None:
        self._importers: list[BaseImporter] = []

    def register(
        self,
        importer: BaseImporter,
    ) -> None:
        """
        Register importer.
        """

        self._importers.append(
            importer
        )

    def get_importer(
        self,
        path: str | Path,
    ) -> BaseImporter | None:
        """
        Find suitable importer.
        """

        for importer in self._importers:

            if importer.supports(path):

                return importer

        return None

    def get_all(
        self,
    ) -> list[BaseImporter]:
        """
        Return registered importers.
        """

        return list(
            self._importers
        )