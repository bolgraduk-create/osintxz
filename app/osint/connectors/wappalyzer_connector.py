"""
Wappalyzer connector.

Detects technologies used by websites.

Responsibilities:

- execute Wappalyzer
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


class WappalyzerConnector(BaseConnector):
    """
    Wappalyzer connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Wappalyzer"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Detect technologies "
            "used by websites."
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
                "wappalyzer",
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
                error="Wappalyzer is not installed.",
            )

        execution = self.runner.run(

            command=[
                "wappalyzer",
                request.target.value,
                "--pretty",
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

        try:

            data = json.loads(
                execution.stdout,
            )

        except Exception as exc:

            return OsintResult(

                connector=self.name,

                status=ResultStatus.PARTIAL,

                execution_time=execution.execution_time,

                error=str(exc),

                raw_data=execution.stdout,

            )

        findings: list[
            OsintFinding
        ] = []

        technologies = data.get(
            "technologies",
            [],
        )

        for tech in technologies:

            findings.append(

                OsintFinding(

                    category="technology",

                    value=tech.get(
                        "name",
                        "Unknown",
                    ),

                    source="Wappalyzer",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=tech,

                )

            )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            findings=findings,

            raw_data=(
                data
                if request.save_raw_output
                else None
            ),

        )

        result.metadata = {

            "technologies_found": result.total_findings,

        }

        return result