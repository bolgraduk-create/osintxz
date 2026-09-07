"""
Assetfinder connector.

Collects subdomains using Assetfinder.

Responsibilities:

- execute Assetfinder
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


class AssetfinderConnector(BaseConnector):
    """
    Assetfinder connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Assetfinder"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Enumerates subdomains using "
            "Tomnomnom Assetfinder."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
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
                "assetfinder",
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
                error="Assetfinder is not installed.",
            )

        execution = self.runner.run(

            [
                "assetfinder",
                "--subs-only",
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

        findings: list[OsintFinding] = []

        for line in execution.stdout.splitlines():

            value = line.strip()

            if not value:
                continue

            findings.append(

                OsintFinding(

                    category="subdomain",

                    value=value,

                    source="Assetfinder",

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

            "records_found": result.total_findings,

        }

        return result