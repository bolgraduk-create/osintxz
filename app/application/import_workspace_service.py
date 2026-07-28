"""
Import workspace application service.

Responsible for:

- coordinating import workflows
- validating investigation case
- delegating import operations

Does NOT:

- parse files
- perform investigation logic
- access repositories directly
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.case_service import (
    CaseService,
)

from app.services.telegram_import_service import (
    TelegramImportService,
)


class ImportWorkspaceService:
    """
    Coordinates import workflows for investigations.
    """

    def __init__(
        self,
        case_service: CaseService,
        telegram_import_service: TelegramImportService,
    ) -> None:

        self.case_service = case_service

        self.telegram_import_service = (
            telegram_import_service
        )

    def import_telegram(
        self,
        case_id: UUID,
        export_path: str | Path,
    ) -> None:
        """
        Import Telegram export into an existing case.
        """

        case = self.case_service.get_case(
            case_id
        )

        if case is None:

            raise ValueError(
                "Case not found."
            )

        self.telegram_import_service.import_export(
            case_id=case_id,
            path=export_path,
        )