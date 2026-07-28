"""
Archive.today connector.

Searches archived snapshots using archive.today.

Responsibilities:

- query archive.today
- parse response
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


class ArchiveTodayConnector(BaseConnector):
    """
    Archive.today connector.
    """

    name = "archivetoday"

    description = (
        "Search archived pages using archive.today."
    )

    supported_targets = {
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

        return shutil.which(
            "curl",
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

        query = (
            "https://archive.today/submit/?url="
            + request.target.value
        )

        execution = self.runner.run(

            [
                "curl",
                "-L",
                "-I",
                query,
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

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            raw_data=(
                execution.stdout
                if request.save_raw_output
                else None
            ),

        )

        snapshot = None

        for line in execution.stdout.splitlines():

            if line.lower().startswith("location:"):

                snapshot = (
                    line.split(
                        ":",
                        1,
                    )[1]
                    .strip()
                )

        if snapshot:

            result.add_finding(

                OsintFinding(

                    category="archive",

                    value=snapshot,

                    source="Archive.today",

                    confidence=1.0,

                    reliability=1.0,

                    metadata={
                        "target": request.target.value,
                    },

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result