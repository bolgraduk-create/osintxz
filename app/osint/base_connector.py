"""
Base OSINT connector.

Defines a common interface for every
external OSINT tool integrated into
the Intelligence Platform.

Responsibilities:

- connector metadata
- capability description
- execution entrypoint
- validation
- availability check

Does NOT:

- parse tool output
- store database objects
- call AI
- perform workflow logic
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any

from app.osint.models import (
    ConnectorRequest,
    OsintTargetType,
)

from app.osint.result import OsintResult


class BaseConnector(ABC):
    """
    Base class for every OSINT connector.
    """

    @property
    @abstractmethod
    def name(
        self,
    ) -> str:
        """
        Connector name.
        """

    @property
    @abstractmethod
    def description(
        self,
    ) -> str:
        """
        Human readable description.
        """

    @property
    @abstractmethod
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:
        """
        Supported target types.
        """

    @abstractmethod
    def is_available(
        self,
    ) -> bool:
        """
        Returns True if the external tool
        is installed and ready.
        """

    def validate_target(
        self,
        request: ConnectorRequest,
    ) -> bool:
        """
        Validate target compatibility.
        """

        return (
            request.target.target_type
            in self.supported_targets
        )

    @abstractmethod
    def execute(
        self,
        request: ConnectorRequest,
        **kwargs: Any,
    ) -> OsintResult:
        """
        Execute OSINT collection.
        """

    def __str__(
        self,
    ) -> str:

        return self.name

    def __repr__(
        self,
    ) -> str:

        return (
            f"{self.__class__.__name__}"
            f"(name={self.name})"
        )