"""
theHarvester connector.

Collects OSINT information
about domains.

Responsibilities:

- execute theHarvester
- parse JSON output
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

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


class TheHarvesterConnector(BaseConnector):
    """
    theHarvester connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "TheHarvester"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Collects emails, hosts, subdomains "
            "and other OSINT information about domains."
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
                "theHarvester",
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
                error="theHarvester is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = Path(temp) / "report"

            execution = self.runner.run(

                [
                    "theHarvester",
                    "-d",
                    request.target.value,
                    "-b",
                    "all",
                    "-f",
                    str(output),
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

            json_file = output.with_suffix(".json")

            if not json_file.exists():

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error="JSON report not produced.",

                )

            try:

                data = json.loads(
                    json_file.read_text(
                        encoding="utf-8",
                    )
                )

            except Exception:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error="Unable to parse JSON output.",

                )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            raw_data=(
                data
                if request.save_raw_output
                else None
            ),

        )

        for category, values in data.items():

            if not isinstance(values, list):
                continue

            for value in values:

                result.add_finding(

                    OsintFinding(

                        category=category,

                        value=str(value),

                        source="theHarvester",

                        confidence=1.0,

                        reliability=1.0,

                        metadata={},

                    )

                )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result