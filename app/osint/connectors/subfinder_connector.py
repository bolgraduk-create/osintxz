"""
Subfinder connector.

Collects subdomains using ProjectDiscovery Subfinder.

Responsibilities:

- execute Subfinder
- parse JSON output
- validate target scope
- deduplicate discovered hosts
- enforce request result budget
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

import json

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


class SubfinderConnector(BaseConnector):
    """
    ProjectDiscovery Subfinder connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Subfinder"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Enumerates subdomains using "
            "ProjectDiscovery Subfinder."
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

        return tool_available(
            "subfinder",
        )

    @staticmethod
    def _normalize_domain(
        value: str,
    ) -> str:

        return (
            str(value)
            .strip()
            .lower()
            .rstrip(".")
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

    @classmethod
    def _is_target_subdomain(
        cls,
        host: str,
        domain: str,
    ) -> bool:

        normalized_host = (
            cls._normalize_domain(
                host,
            )
        )

        return (
            bool(normalized_host)
            and normalized_host != domain
            and normalized_host.endswith(
                f".{domain}"
            )
        )

    @staticmethod
    def _provider_timeout(
        request_timeout: int,
    ) -> int:
        """
        Keep individual passive-source waits bounded.

        Subfinder's own provider timeout is separate from the
        outer ToolRunner timeout.
        """

        timeout = max(
            1,
            int(request_timeout),
        )

        return max(
            5,
            min(
                30,
                timeout // 4,
            ),
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
                error="Subfinder is not installed.",
            )

        domain = self._normalize_domain(
            request.target.value,
        )

        if not domain:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error="Empty domain target.",
            )

        result_limit = self._result_limit(
            request,
        )

        provider_timeout = (
            self._provider_timeout(
                request.timeout,
            )
        )

        max_time_minutes = max(
            1,
            min(
                5,
                (
                    max(
                        1,
                        int(request.timeout),
                    )
                    + 59
                )
                // 60,
            ),
        )

        command = build_tool_command(
            "subfinder",
            "-d",
            domain,
            "-oJ",
            "-duc",
            "-timeout",
            str(provider_timeout),
            "-max-time",
            str(max_time_minutes),
        )

        execution = self.runner.run(
            command,
            timeout=request.timeout,
        )

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
                    or "Subfinder execution failed."
                ),
            )

        findings: list[
            OsintFinding
        ] = []

        seen_hosts: set[str] = set()

        parse_errors = 0
        filtered_out = 0
        duplicates_removed = 0
        limit_reached = False

        for line in execution.stdout.splitlines():

            raw_line = line.strip()

            if not raw_line:
                continue

            try:
                item = json.loads(
                    raw_line,
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

            host = self._normalize_domain(
                str(
                    item.get(
                        "host",
                        "",
                    )
                )
            )

            if not self._is_target_subdomain(
                host,
                domain,
            ):
                filtered_out += 1
                continue

            if host in seen_hosts:
                duplicates_removed += 1
                continue

            if (
                result_limit is not None
                and len(findings) >= result_limit
            ):
                limit_reached = True
                break

            seen_hosts.add(
                host,
            )

            metadata = dict(
                item,
            )

            metadata[
                "target_domain"
            ] = domain

            findings.append(
                OsintFinding(
                    category="subdomain",
                    value=host,
                    source="Subfinder",
                    confidence=1.0,
                    reliability=1.0,
                    metadata=metadata,
                )
            )

        timed_out = (
            execution.return_code == -1
        )

        if timed_out and findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                execution.stderr
                or "Subfinder timed out after returning partial results."
            )

        elif timed_out:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "Subfinder timed out."
            )

        elif parse_errors and findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                "Some Subfinder output lines "
                "could not be parsed."
            )

        elif parse_errors and not findings:

            status = (
                ResultStatus.FAILED
            )

            error = (
                "Subfinder returned no usable "
                "JSON findings."
            )

        elif execution.success:

            status = (
                ResultStatus.SUCCESS
            )

            error = None

        else:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "Subfinder execution failed."
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
            "filtered_out": filtered_out,
            "parse_errors": parse_errors,
            "timed_out": timed_out,
            "target_domain": domain,
            "result_limit": result_limit,
            "limit_reached": limit_reached,
        }

        return result
