"""
Nuclei connector.

Scans targets using ProjectDiscovery Nuclei.

Responsibilities:

- execute Nuclei
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


class NucleiConnector(BaseConnector):
    """
    Nuclei connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Nuclei"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Scan targets using "
            "ProjectDiscovery Nuclei."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
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
            shutil.which(
                "nuclei",
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
                error="Nuclei is not installed.",
            )

        execution = self.runner.run(

            command=[
                "nuclei",
                "-u",
                request.target.value,
                "-json",
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

                item = json.loads(line)

                findings.append(

                    OsintFinding(

                        category="vulnerability",

                        value=item.get(
                            "template-id",
                            "Unknown",
                        ),

                        source="Nuclei",

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

            "findings": result.total_findings,

        }

        return result