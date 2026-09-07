"""
Import controller.

Responsible for:

- receiving import requests from UI
- validating import paths
- delegating import to application layer

Does NOT:

- parse Telegram exports
- access repositories
- execute business logic
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.application.import_workspace_service import (
    ImportWorkspaceService,
)


class ImportController:
    """
    Desktop controller for import operations.
    """

    def __init__(
        self,
        import_service: ImportWorkspaceService,
    ) -> None:

        self.import_service = import_service

    # ==========================================================
    # Telegram
    # ==========================================================

    def import_telegram(
        self,
        case_id: UUID,
        export_path: str,
    ):
        """
        Import Telegram export into case.
        """

        path = Path(export_path)

        if not path.exists():

            raise FileNotFoundError(
                export_path
            )

        return self.import_service.import_telegram(
            case_id=case_id,
            export_path=path,
        )

    # ==========================================================
    # Generic
    # ==========================================================

    def import_directory(
        self,
        case_id: UUID,
        directory: str,
    ):
        """
        Placeholder.

        Generic directory import
        will be implemented later.
        """

        raise NotImplementedError(
            "Directory import is not implemented yet."
        )