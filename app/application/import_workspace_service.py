"""
Import workspace application service.

Responsible for:

- coordinating import workflows
- validating investigation case
- delegating import operations
- returning import statistics to controllers and UI

Does NOT:

- parse files
- perform investigation logic
- access repositories directly
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from app.services.case_service import (
    CaseService,
)

from app.services.telegram_import_service import (
    TelegramImportService,
)


class ImportWorkspaceService:
    """
    Coordinates import workflows.
    """

    def __init__(
        self,
        case_service: CaseService,
        telegram_import_service: TelegramImportService,
    ) -> None:

        self.case_service = (
            case_service
        )

        self.telegram_import_service = (
            telegram_import_service
        )

    # ==========================================================
    # Validation
    # ==========================================================

    def validate_case(
        self,
        case_id: UUID,
    ) -> bool:
        """
        Ensure that the investigation case exists.
        """

        return (
            self.case_service.get_case(
                case_id
            )
            is not None
        )

    # ==========================================================
    # Telegram
    # ==========================================================

    def import_telegram(
        self,
        case_id: UUID,
        export_path: str | Path,
    ) -> dict[str, Any]:
        """
        Import Telegram export and return import statistics.
        """

        if not self.validate_case(
            case_id
        ):

            raise ValueError(
                "Case not found."
            )

        return (
            self.telegram_import_service
            .import_export(
                case_id=case_id,
                export_path=export_path,
            )
        )

    # ==========================================================
    # Generic directory
    # ==========================================================

    def import_directory(
        self,
        case_id: UUID,
        directory: str | Path,
    ) -> dict[str, Any]:
        """
        Generic directory import.

        Will be connected when additional
        collectors are implemented.
        """

        if not self.validate_case(
            case_id
        ):

            raise ValueError(
                "Case not found."
            )

        raise NotImplementedError(
            "Directory import is not implemented yet."
        )

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, str]:
        """
        Return service metadata.
        """

        return {
            "type": (
                "import_workspace_service"
            ),
            "version": "2.0",
        }