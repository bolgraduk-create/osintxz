"""
Amass connector.

Collects DNS and subdomain
information using OWASP Amass.

Responsibilities:

- execute Amass
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


class AmassConnector(BaseConnector):
    """
    OWASP Amass connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Amass"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Enumerates subdomains and DNS "
            "information using OWASP Amass."
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
                "amass",
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
                error="Amass is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            json_file = Path(temp) / "amass.json"

            execution = self.runner.run(

                [
                    "amass",
                    "enum",
                    "-d",
                    request.target.value,
                    "-json",
                    str(json_file),
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

            if not json_file.exists():

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error="JSON output not produced.",

                )

            findings: list[OsintFinding] = []

            try:

                with json_file.open(
                    "r",
                    encoding="utf-8",
                ) as file:

                    for line in file:

                        if not line.strip():
                            continue

                        item = json.loads(line)

                        findings.append(

                            OsintFinding(

                                category="subdomain",

                                value=item.get(
                                    "name",
                                    "",
                                ),

                                source="Amass",

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
                findings
                if request.save_raw_output
                else None
            ),

        )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result