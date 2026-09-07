"""
File import controller.

Responsible for:

- receiving UI import requests
- controlling transaction boundaries
- delegating import to FileImportService

Does NOT:

- copy files
- access repositories
- analyze media
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.file_import_service import (
    FileImportService,
)


class FileImportController:
    """
    Desktop controller for importing files.
    """

    def __init__(
        self,
        container,
        file_import_service: FileImportService,
    ) -> None:

        self.container = container

        self.file_import_service = (
            file_import_service
        )

    # ==========================================================
    # Import
    # ==========================================================

    def import_file(
        self,
        case_id: str | UUID,
        file_path: str | Path,
    ) -> dict:

        try:

            result = (
                self.file_import_service
                .import_file(
                    case_id=case_id,
                    file_path=file_path,
                )
            )

            self.container.commit()

            return result

        except Exception:

            self.container.rollback()

            raise

    def import_files(
        self,
        case_id: str | UUID,
        file_paths: list[str | Path],
    ) -> dict:

        try:

            result = (
                self.file_import_service
                .import_files(
                    case_id=case_id,
                    file_paths=file_paths,
                )
            )

            self.container.commit()

            return result

        except Exception:

            self.container.rollback()

            raise