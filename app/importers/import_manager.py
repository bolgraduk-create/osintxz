"""
Import manager.

Coordinates the import process.

Responsibilities:

- select appropriate importer
- execute import
- provide a single entry point

Does NOT:

- parse files
- process data
- access the database directly
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from app.importers.importer_factory import ImporterFactory


class ImportManager:
    """
    Main entry point for all imports.
    """

    def __init__(self) -> None:

        self.registry = (
            ImporterFactory.create_registry()
        )

    # ==========================================================
    # Import
    # ==========================================================

    def import_file(
        self,
        case_id: UUID,
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Import external file.
        """

        importer = (
            self.registry.get_importer(path)
        )

        if importer is None:

            raise ValueError(
                f"No importer found for '{path}'."
            )

        return importer.import_data(
            case_id=case_id,
            source=str(path),
        )

    # ==========================================================
    # Information
    # ==========================================================

    def supported_importers(
        self,
    ) -> list[str]:
        """
        Return registered importers.
        """

        return [

            importer.name

            for importer in self.registry.get_all()

        ]