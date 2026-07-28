"""
CloudEnum connector.

Searches cloud storage assets
using CloudEnum.

Responsibilities:

- execute CloudEnum
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


class CloudEnumConnector(BaseConnector):
    """
    CloudEnum connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "CloudEnum"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Enumerate cloud assets "
            "using CloudEnum."
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
                "cloudenum",
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
                error="CloudEnum is not installed.",
            )

        execution = self.runner.run(

            command=[
                "cloudenum",
                "-k",
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

            value = line.strip()

            if not value:
                continue

            findings.append(

                OsintFinding(

                    category="cloud_asset",

                    value=value,

                    source="CloudEnum",

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

            "assets_found": result.total_findings,

        }

        return result