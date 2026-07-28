"""
Investigation application service.

Top-level application service.

Responsibilities:

- create investigation case
- execute import workflow

Does NOT:

- implement business logic
- perform analysis
- access repositories directly
"""

from __future__ import annotations

from pathlib import Path

from app.models.case import Case

from app.services.case_service import (
    CaseService,
)

from app.services.import_service import (
    ImportService,
)


class InvestigationApplicationService:
    """
    High-level investigation application service.
    """

    def __init__(
        self,
        case_service: CaseService,
        import_service: ImportService,
    ) -> None:

        self.case_service = case_service

        self.import_service = import_service

    def create_case_and_import_telegram(
        self,
        title: str,
        export_path: str | Path,
        description: str | None = None,
    ) -> Case:
        """
        Create investigation case
        and import Telegram export.
        """

        case = self.case_service.create_case(
            title=title,
            description=description,
        )

        self.import_service.import_telegram(
            case_id=case.id,
            export_path=export_path,
        )

        return case