"""
OSINT investigation pipeline.

Runs all registered OSINT connectors
for a single investigation target.

Responsibilities:

- execute every connector
- collect results
- isolate connector failures

Does NOT:

- store data
- call AI
- access database
"""

from __future__ import annotations

from app.osint.manager import OsintManager
from app.osint.models import ConnectorRequest
from app.osint.result import (
    OsintResult,
    ResultStatus,
)


class OsintPipeline:
    """
    Executes OSINT investigations.
    """

    def __init__(
        self,
        manager: OsintManager,
    ) -> None:

        self.manager = manager


    def run(
        self,
        request: ConnectorRequest,
    ) -> list[OsintResult]:
        """
        Execute every compatible connector.
        """

        results: list[OsintResult] = []

        connectors = self.manager.registry.supported(
            request.target.target_type,
        )


        for connector in connectors:

            try:

                results.append(
                    connector.execute(
                        request,
                    )
                )

            except Exception as exc:

                results.append(

                    OsintResult(

                        connector=connector.name,

                        status=ResultStatus.FAILED,

                        error=str(exc),

                    )

                )


        return results


    def run_connector(
        self,
        connector_name: str,
        request: ConnectorRequest,
    ) -> OsintResult | None:
        """
        Execute one connector.
        """

        connector = self.manager.registry.get(
            connector_name,
        )

        if connector is None:
            return None


        try:

            return connector.execute(
                request,
            )

        except Exception as exc:

            return OsintResult(

                connector=connector.name,

                status=ResultStatus.FAILED,

                error=str(exc),

            )


    def available_connectors(
        self,
    ) -> list[str]:
        """
        Return connector names.
        """

        return self.manager.registry.names()