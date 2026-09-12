"""
httpx connector.

Performs HTTP probing using
ProjectDiscovery httpx.

Responsibilities:

- execute ProjectDiscovery httpx
- parse JSONL output safely
- deduplicate probe findings
- honor ConnectorRequest.limit
- preserve partial findings on timeout
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

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
from app.osint.tool_runtime import (
    build_tool_command,
    tool_available,
)


class HTTPXConnector(BaseConnector):
    """
    ProjectDiscovery httpx connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "HTTPX"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Performs HTTP probing using "
            "ProjectDiscovery HTTPX."
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

        return tool_available(
            "httpx",
        )

    @staticmethod
    def _result_limit(
        request: ConnectorRequest,
    ) -> int | None:

        if request.limit is None:
            return None

        return max(
            0,
            int(request.limit),
        )

    @staticmethod
    def _dedupe_key(
        value: str,
    ) -> tuple[
        str,
        str,
        int | None,
        str,
        str,
    ] | tuple[
        str,
    ]:

        try:

            parsed = urlsplit(
                value,
            )

            if (
                parsed.scheme
                and parsed.hostname
            ):

                return (
                    parsed.scheme.lower(),
                    parsed.hostname.lower(),
                    parsed.port,
                    parsed.path or "/",
                    parsed.query,
                )

        except ValueError:
            pass

        return (
            value.strip(),
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
                error="ProjectDiscovery HTTPX is not installed.",
            )

        result_limit = self._result_limit(
            request,
        )

        if result_limit == 0:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                metadata={
                    "records_found": 0,
                    "duplicates_removed": 0,
                    "parse_errors": 0,
                    "timed_out": False,
                    "result_limit": 0,
                    "limit_reached": True,
                },
            )

        target_value = str(
            request.target.value
        ).strip()

        command = build_tool_command(
            "httpx",
            "-u",
            target_value,
            "-silent",
            "-json",
            "-sc",
            "-duc",
        )

        execution = self.runner.run(
            command=command,
            timeout=request.timeout,
        )

        # A non-timeout CLI failure with no usable output is a hard failure.
        if (
            not execution.success
            and execution.return_code != -1
            and not execution.stdout.strip()
        ):

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                execution_time=execution.execution_time,
                error=(
                    execution.stderr
                    or "HTTPX execution failed."
                ),
            )

        findings: list[
            OsintFinding
        ] = []

        seen: set[
            tuple
        ] = set()

        parse_errors = 0
        duplicates_removed = 0
        limit_reached = False

        for raw_line in (
            execution.stdout.splitlines()
        ):

            line = raw_line.strip()

            if not line:
                continue

            try:

                item = json.loads(
                    line,
                )

            except json.JSONDecodeError:

                parse_errors += 1
                continue

            if not isinstance(
                item,
                dict,
            ):

                parse_errors += 1
                continue

            value = str(
                item.get(
                    "url",
                    target_value,
                )
                or target_value
            ).strip()

            if not value:
                parse_errors += 1
                continue

            key = self._dedupe_key(
                value,
            )

            if key in seen:

                duplicates_removed += 1
                continue

            if (
                result_limit is not None
                and len(findings) >= result_limit
            ):

                limit_reached = True
                break

            seen.add(
                key,
            )

            findings.append(
                OsintFinding(
                    category="http",
                    value=value,
                    url=value,
                    source="HTTPX",
                    confidence=1.0,
                    reliability=1.0,
                    metadata=item,
                )
            )

        if (
            result_limit is not None
            and len(findings) >= result_limit
        ):

            limit_reached = True

        timed_out = (
            execution.return_code == -1
        )

        if timed_out and findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                execution.stderr
                or "HTTPX timed out after returning partial results."
            )

        elif timed_out:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "HTTPX timed out."
            )

        elif parse_errors and findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                "Some HTTPX JSONL records "
                "could not be parsed."
            )

        elif parse_errors and not findings:

            status = (
                ResultStatus.FAILED
            )

            error = (
                "HTTPX returned no usable "
                "JSONL findings."
            )

        elif execution.success:

            status = (
                ResultStatus.SUCCESS
            )

            error = None

        elif findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                execution.stderr
                or "HTTPX returned partial output."
            )

        else:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "HTTPX execution failed."
            )

        result = OsintResult(
            connector=self.name,
            status=status,
            execution_time=execution.execution_time,
            findings=findings,
            raw_data=(
                execution.stdout
                if request.save_raw_output
                else None
            ),
            error=error,
        )

        result.metadata = {
            "records_found": result.total_findings,
            "duplicates_removed": duplicates_removed,
            "parse_errors": parse_errors,
            "timed_out": timed_out,
            "result_limit": result_limit,
            "limit_reached": limit_reached,
        }

        if (
            request.include_metadata
            and execution.stderr.strip()
            and execution.success
        ):

            result.metadata[
                "tool_warnings"
            ] = execution.stderr.strip()[:2000]

        return result
