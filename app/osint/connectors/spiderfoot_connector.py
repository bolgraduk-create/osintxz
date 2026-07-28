"""
SpiderFoot connector.

Runs SpiderFoot scans through CLI/API.

Responsibilities:

- execute SpiderFoot
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


class SpiderFootConnector(BaseConnector):
    """
    SpiderFoot connector.
    """

    name = "spiderfoot"

    description = (
        "Automated OSINT investigation using SpiderFoot."
    )

    supported_targets = {
        OsintTargetType.DOMAIN,
        OsintTargetType.IP,
        OsintTargetType.EMAIL,
        OsintTargetType.USERNAME,
    }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return (
            shutil.which("spiderfoot")
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
                error="SpiderFoot is not installed.",
            )

        with tempfile.TemporaryDirectory() as tmp:

            output = (
                Path(tmp)
                / "spiderfoot.json"
            )

            execution = self.runner.run(
                [
                    "spiderfoot",
                    "-s",
                    request.target.value,
                    "-o",
                    "json",
                    "-O",
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

            if not output.exists():

                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    error="SpiderFoot produced no JSON output.",
                )

            try:

                data = json.loads(
                    output.read_text(
                        encoding="utf-8",
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
            raw_data=(
                data
                if request.save_raw_output
                else None
            ),
        )

        if isinstance(data, list):

            for item in data:

                result.add_finding(

                    OsintFinding(

                        category=item.get(
                            "type",
                            "osint",
                        ),

                        value=str(
                            item.get(
                                "data",
                                "",
                            )
                        ),

                        source="SpiderFoot",

                        confidence=1.0,

                        reliability=1.0,

                        metadata=item,

                    )

                )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result