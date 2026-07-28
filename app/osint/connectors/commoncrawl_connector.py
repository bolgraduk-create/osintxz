"""
Common Crawl connector.

Searches historical URLs using the Common Crawl index.

Responsibilities:

- query Common Crawl index
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


class CommonCrawlConnector(BaseConnector):
    """
    Common Crawl connector.
    """

    name = "commoncrawl"

    description = (
        "Search historical URLs using Common Crawl."
    )

    supported_targets = {
        OsintTargetType.DOMAIN,
        OsintTargetType.URL,
    }

    def __init__(self) -> None:
        self.runner = ToolRunner()

    def is_available(self) -> bool:
        return shutil.which("curl") is not None

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

        url = (
            "https://index.commoncrawl.org/"
            "CC-MAIN-latest-index"
            "?url="
            + request.target.value
            + "&output=json"
        )

        execution = self.runner.run(
            [
                "curl",
                "-L",
                url,
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

        try:

            for line in execution.stdout.splitlines():

                if not line.strip():
                    continue

                item = json.loads(line)

                result.add_finding(

                    OsintFinding(

                        category="historical_url",

                        value=item.get(
                            "url",
                            "",
                        ),

                        source="Common Crawl",

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
                raw_data=execution.stdout,
            )

        result.metadata = {
            "records_found": result.total_findings,
        }

        return result