"""
OSINT connector registry.

Stores every available connector.

Responsibilities:

- register connectors
- unregister connectors
- find connectors
- return compatible connectors

Does NOT:

- execute connectors
- call AI
- access database
"""

from __future__ import annotations

from app.osint.base_connector import BaseConnector
from app.osint.models import OsintTargetType


class ConnectorRegistry:
    """
    Registry of OSINT connectors.
    """

    def __init__(
        self,
    ) -> None:

        self._connectors: dict[
            str,
            BaseConnector,
        ] = {}

    def register(
        self,
        connector: BaseConnector,
    ) -> None:
        """
        Register connector.
        """

        self._connectors[
            connector.name.lower()
        ] = connector

    def unregister(
        self,
        connector_name: str,
    ) -> None:
        """
        Remove connector.
        """

        self._connectors.pop(
            connector_name.lower(),
            None,
        )

    def get(
        self,
        connector_name: str,
    ) -> BaseConnector | None:
        """
        Return connector by name.
        """

        return self._connectors.get(
            connector_name.lower(),
        )

    def all(
        self,
    ) -> list[BaseConnector]:
        """
        Return every registered connector.
        """

        return list(
            self._connectors.values()
        )

    def names(
        self,
    ) -> list[str]:
        """
        Return connector names.
        """

        return sorted(
            self._connectors.keys()
        )

    def supported(
        self,
        target_type: OsintTargetType,
    ) -> list[BaseConnector]:
        """
        Return compatible connectors.
        """

        compatible: list[
            BaseConnector
        ] = []

        for connector in self._connectors.values():

            if (
                target_type
                in connector.supported_targets
            ):
                compatible.append(
                    connector
                )

        return compatible

    def clear(
        self,
    ) -> None:
        """
        Remove every connector.
        """

        self._connectors.clear()

    def __contains__(
        self,
        connector_name: str,
    ) -> bool:

        return (
            connector_name.lower()
            in self._connectors
        )

    def __len__(
        self,
    ) -> int:

        return len(
            self._connectors
        )

    def __iter__(
        self,
    ):

        return iter(
            self._connectors.values()
        )