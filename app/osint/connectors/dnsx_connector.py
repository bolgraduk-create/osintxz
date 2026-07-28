"""
dnsx connector.

Performs DNS resolution using
ProjectDiscovery dnsx.

Responsibilities:

- execute dnsx
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


class DNSXConnector(BaseConnector):
    """
    dnsx connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "DNSX"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Resolves DNS records using "
            "ProjectDiscovery DNSX."
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
                "dnsx",
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
                error="DNSX is not installed.",
            )

        execution = self.runner.run(

            command=[
                "dnsx",
                "-silent",
                "-json",
            ],

            stdin=request.target.value,

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

                item = json.loads(line)

                findings.append(

                    OsintFinding(

                        category="dns",

                        value=item.get(
                            "host",
                            request.target.value,
                        ),

                        source="DNSX",

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

            "records_found": result.total_findings,

        }

        return result