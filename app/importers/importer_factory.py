"""
Importer factory.

Creates and registers all available
importers.
"""

from __future__ import annotations

from app.importers.importer_registry import (
    ImporterRegistry,
)

from app.importers.telegram_importer import (
    TelegramImporter,
)


class ImporterFactory:
    """
    Factory responsible for building
    importer registry.
    """

    @staticmethod
    def create_registry() -> ImporterRegistry:
        """
        Create importer registry.
        """

        registry = ImporterRegistry()

        # Telegram
        registry.register(
            TelegramImporter()
        )

        return registry