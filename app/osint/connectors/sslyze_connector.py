"""
SSLyze connector.

Analyzes SSL/TLS configuration
using SSLyze.

Responsibilities:

- execute SSLyze
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


class SSLyzeConnector(BaseConnector):
    """
    SSLyze connector.
    """

    name = "sslyze"

    description = (
        "Analyze SSL/TLS configuration using SSLyze."
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

        return shutil.which(
            "sslyze",
        ) is not None

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
                error="SSLyze is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = Path(temp) / "sslyze.json"

            execution = self.runner.run(

                [
                    "sslyze",
                    "--json_out",
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

                    error="SSLyze produced no JSON output.",

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

        for server in data.get(
            "server_scan_results",
            [],
        ):

            result.add_finding(

                OsintFinding(

                    category="tls",

                    value=server.get(
                        "server_location",
                        request.target.value,
                    ),

                    source="SSLyze",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=server,

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result