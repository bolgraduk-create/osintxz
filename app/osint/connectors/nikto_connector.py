"""
Nikto connector.

Performs web vulnerability scanning
using Nikto.

Responsibilities:

- execute Nikto
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


class NiktoConnector(BaseConnector):
    """
    Nikto connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Nikto"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Web vulnerability scanner "
            "using Nikto."
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
                "nikto",
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
                error="Nikto is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            report = Path(temp) / "nikto.json"

            execution = self.runner.run(

                command=[
                    "nikto",
                    "-h",
                    request.target.value,
                    "-Format",
                    "json",
                    "-output",
                    str(report),
                ],

                timeout=request.timeout,

            )

            if (
                not execution.success
                and not report.exists()
            ):

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.FAILED,

                    execution_time=execution.execution_time,

                    error=execution.stderr,

                )

            try:

                if report.exists():

                    data = json.loads(
                        report.read_text(
                            encoding="utf-8",
                        )
                    )

                else:

                    data = {}

            except Exception as exc:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error=str(exc),

                )

        findings: list[
            OsintFinding
        ] = []

        for item in data.get(
            "vulnerabilities",
            [],
        ):

            findings.append(

                OsintFinding(

                    category="vulnerability",

                    value=item.get(
                        "msg",
                        "Unknown",
                    ),

                    source="Nikto",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=item,

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

            "vulnerabilities_found": result.total_findings,

        }

        return result