"""
Telegram importer.

Imports Telegram exports into
the investigation platform.

Responsibilities:

- validate Telegram export
- use TelegramCollector
- return collected data

Does NOT:

- perform analysis
- resolve entities
- save into database
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.collection.telegram_collector import TelegramCollector

from app.importers.base_importer import BaseImporter


class TelegramImporter(BaseImporter):
    """
    Telegram data importer.
    """

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:
        return (
            ".json",
        )

    def __init__(
        self,
        collector: TelegramCollector | None = None,
    ):
        self.collector = (
            collector
            or TelegramCollector()
        )

    def validate(
        self,
        path: str | Path,
    ) -> bool:
        """
        Validate Telegram export.
        """

        path = Path(path)

        return (
            path.exists()
            and path.is_file()
            and self.supports(path)
        )

    def import_data(
        self,
        path: str | Path,
        **kwargs: Any,
    ) -> Any:
        """
        Import Telegram export.
        """

        return self.collector.collect(
            Path(path)
        )