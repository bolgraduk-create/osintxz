"""
TruffleHog connector.

Searches repositories and targets
for leaked secrets.

Responsibilities:

- execute TruffleHog
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


class TruffleHogConnector(BaseConnector):
    """
    TruffleHog connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "TruffleHog"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Search for leaked credentials "
            "using TruffleHog."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
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
                "trufflehog",
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
                error="TruffleHog is not installed.",
            )

        execution = self.runner.run(

            command=[
                "trufflehog",
                "filesystem",
                request.target.value,
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

        findings: list[
            OsintFinding
        ] = []

        try:

            for line in execution.stdout.splitlines():

                if not line.strip():
                    continue

                item = json.loads(
                    line,
                )

                findings.append(

                    OsintFinding(

                        category="secret",

                        value=item.get(
                            "DetectorName",
                            "Secret",
                        ),

                        source="TruffleHog",

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

            "secrets_found": result.total_findings,

        }

        return result