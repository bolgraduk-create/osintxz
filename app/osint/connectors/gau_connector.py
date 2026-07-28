"""
GAU connector.

Collects historical URLs using
GetAllURLs (gau).

Responsibilities:

- execute gau
- parse output
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

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


class GauConnector(BaseConnector):
    """
    GAU connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "GAU"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Collect historical URLs "
            "using GetAllURLs."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.DOMAIN,
            OsintTargetType.URL,
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
                "gau",
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
                error="GAU is not installed.",
            )

        execution = self.runner.run(

            command=[
                "gau",
                request.target.value,
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

        findings: list[
            OsintFinding
        ] = []

        for line in execution.stdout.splitlines():

            url = line.strip()

            if not url:
                continue

            findings.append(

                OsintFinding(

                    category="historical_url",

                    value=url,

                    url=url,

                    source="GAU",

                    confidence=1.0,

                    reliability=1.0,

                    metadata={},

                )

            )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            findings=findings,

            raw_data=(
                execution.stdout
                if request.save_raw_output
                else None
            ),

        )

        result.metadata = {

            "urls_found": result.total_findings,

        }

        return result