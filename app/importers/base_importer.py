"""
Base importer.

Defines a common interface for every
data importer.

Responsibilities:

- validate input
- import external data
- return import result

Does NOT:

- perform analysis
- resolve entities
- call AI
- generate reports
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from pathlib import Path
from typing import Any


class BaseImporter(ABC):
    """
    Base class for every importer.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Importer name.
        """

    @property
    @abstractmethod
    def supported_extensions(
        self,
    ) -> tuple[str, ...]:
        """
        Supported file extensions.
        """

    def supports(
        self,
        path: str | Path,
    ) -> bool:
        """
        Check whether importer
        supports given file.
        """

        suffix = Path(path).suffix.lower()

        return suffix in self.supported_extensions

    @abstractmethod
    def validate(
        self,
        path: str | Path,
    ) -> bool:
        """
        Validate import source.
        """

    @abstractmethod
    def import_data(
        self,
        path: str | Path,
        **kwargs: Any,
    ) -> Any:
        """
        Import external data.
        """

    def __call__(
        self,
        path: str | Path,
        **kwargs: Any,
    ) -> Any:
        """
        Shortcut for import.
        """

        if not self.validate(path):
            raise ValueError(
                f"Invalid import source: {path}"
            )

        return self.import_data(
            path,
            **kwargs,
        )