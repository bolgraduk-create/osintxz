"""
Investigation runner service.

High-level application service that executes
a complete investigation workflow.

Responsibilities:

- start investigation
- coordinate import
- execute pipeline

Does NOT:

- parse Telegram
- perform AI analysis
- implement business logic
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.services.telegram_import_service import (
    TelegramImportService,
)


class InvestigationRunnerService:
    """
    High-level investigation workflow.
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
        Import Telegram export
        into investigation.
        """

        self.telegram_import_service.import_export(
            case_id=case_id,
            path=export_path,
        )