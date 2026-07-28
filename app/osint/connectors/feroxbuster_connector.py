"""
Feroxbuster connector.

Performs directory enumeration
using Feroxbuster.

Responsibilities:

- execute Feroxbuster
- parse JSON output
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

import json
import shutil

from app.osint.base_connector import BaseConnector
from app.osint.models import (
    ConnectorRequest,
    OsintTargetType,
)
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)
from app.osint.runner import ToolRunner


class FeroxbusterConnector(BaseConnector):
    """
    Feroxbuster connector.
    """

    name = "feroxbuster"

    description = (
        "Fast content discovery using Feroxbuster."
    )

    supported_targets = {
        OsintTargetType.URL,
        OsintTargetType.DOMAIN,
    }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return (
            shutil.which(
                "feroxbuster",
            )
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:

        if (
            request.target.target_type
            not in self.supported_targets
        ):
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        if not self.is_available():

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="Feroxbuster is not installed.",
            )

        execution = self.runner.run(

            [
                "feroxbuster",
                "--url",
                request.target.value,
                "--silent",
                "--json",
            ],

            timeout=request.timeout,

        )

        if not execution.success:

            return OsintResult(

                connector=self.name,

                status=ResultStatus.FAILED,

                execution_time=execution.execution_time,

                error=execution.stderr,

            )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            raw_data=(
                execution.stdout
                if request.save_raw_output
                else None
            ),

        )

        try:

            for line in execution.stdout.splitlines():

                if not line.strip():
                    continue

                item = json.loads(line)

                result.add_finding(

                    OsintFinding(

                        category="endpoint",

                        value=item.get(
                            "url",
                            "",
                        ),

                        source="Feroxbuster",

                        confidence=1.0,

                        reliability=1.0,

                        metadata=item,

                    )

                )

        except Exception as exc:

            return OsintResult(

                connector=self.name,

                status=ResultStatus.PARTIAL,

                execution_time=execution.execution_time,

                error=str(exc),

                raw_data=execution.stdout,

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result