"""
Import service.

Unified entry point for all data imports.

Responsibilities:

- execute import workflows
- select proper importer

Does NOT:

- parse files
- perform investigation
- implement business logic
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.telegram_import_service import (
    TelegramImportService,
)


class ImportService:
    """
    Unified investigation import service.
    """

    def __init__(
        self,
        telegram_import_service: TelegramImportService,
    ) -> None:

        self.telegram_import_service = (
            telegram_import_service
        )

    def import_telegram(
        self,
        case_id: UUID,
        export_path: str | Path,
    ) -> None:
        """
        Import Telegram export.
        """

        self.telegram_import_service.import_export(
            case_id=case_id,
            path=export_path,
        )