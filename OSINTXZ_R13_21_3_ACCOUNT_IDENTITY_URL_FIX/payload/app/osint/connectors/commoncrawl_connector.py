"""
Common Crawl connector.

Searches historical URLs using the Common Crawl index.

R13.21.3 hardening:
- ignore non-object NDJSON rows instead of calling .get() on strings/lists;
- isolate malformed lines without turning otherwise usable output into noise.
"""

from __future__ import annotations

import json
import shutil

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class CommonCrawlConnector(BaseConnector):
    name = "commoncrawl"
    description = "Search historical URLs using Common Crawl."
    supported_targets = {OsintTargetType.DOMAIN, OsintTargetType.URL}

    def __init__(self) -> None:
        self.runner = ToolRunner()

    def is_available(self) -> bool:
        return shutil.which("curl") is not None

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        url = (
            "https://index.commoncrawl.org/"
            "CC-MAIN-latest-index"
            "?url=" + request.target.value + "&output=json"
        )

        execution = self.runner.run(["curl", "-L", url], timeout=request.timeout)
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
            raw_data=execution.stdout if request.save_raw_output else None,
        )

        malformed_rows = 0
        non_object_rows = 0
        for line in execution.stdout.splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                malformed_rows += 1
                continue
            if not isinstance(item, dict):
                non_object_rows += 1
                continue

            found_url = str(item.get("url") or "").strip()
            if not found_url:
                continue
            result.add_finding(
                OsintFinding(
                    category="historical_url",
                    value=found_url,
                    source="Common Crawl",
                    confidence=1.0,
                    reliability=1.0,
                    metadata=item,
                )
            )

        result.metadata = {
            "records_found": result.total_findings,
            "malformed_rows_skipped": malformed_rows,
            "non_object_rows_skipped": non_object_rows,
        }
        return result
