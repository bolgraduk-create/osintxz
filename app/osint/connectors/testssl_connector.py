"""
testssl.sh connector.

Analyzes SSL/TLS configuration
using testssl.sh.

Responsibilities:

- execute testssl.sh
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


class TestSSLConnector(BaseConnector):
    """
    testssl.sh connector.
    """

    name = "testssl"

    description = (
        "Analyze SSL/TLS configuration using testssl.sh."
    )

    supported_targets = {
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
            shutil.which("testssl.sh")
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
                error="testssl.sh is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = (
                Path(temp)
                / "testssl.json"
            )

            execution = self.runner.run(

                [
                    "testssl.sh",
                    "--quiet",
                    "--jsonfile",
                    str(output),
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

            if not output.exists():

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error="testssl.sh produced no JSON output.",

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

                        category="tls",

                        value=item.get(
                            "id",
                            "tls",
                        ),

                        source="testssl.sh",

                        confidence=1.0,

                        reliability=1.0,

                        metadata=item,

                    )

                )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result