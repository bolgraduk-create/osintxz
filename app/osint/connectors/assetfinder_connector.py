"""
Assetfinder connector.

Collects subdomains using Assetfinder.

Responsibilities:

- execute Assetfinder
- normalize and deduplicate subdomains
- enforce request result budget
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

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


class AssetfinderConnector(BaseConnector):
    """
    Assetfinder connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Assetfinder"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Enumerates subdomains using "
            "Tomnomnom Assetfinder."
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
            "assetfinder",
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
                error="Assetfinder is not installed.",
            )

        domain = self._normalize_domain(
            request.target.value,
        )

        execution = self.runner.run(
            build_tool_command(
                "assetfinder",
                "--subs-only",
                domain,
            ),
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

        seen_hosts: set[str] = set()

        result_limit = self._result_limit(
            request,
        )

        duplicates_removed = 0
        filtered_out = 0
        limit_reached = False

        for line in execution.stdout.splitlines():

            value = self._normalize_domain(
                line,
            )

            if not value:
                continue

            if (
                value == domain
                or not value.endswith(
                    f".{domain}"
                )
            ):
                filtered_out += 1
                continue

            if value in seen_hosts:
                duplicates_removed += 1
                continue

            if (
                result_limit is not None
                and len(findings) >= result_limit
            ):
                limit_reached = True
                break

            seen_hosts.add(
                value,
            )

            findings.append(
                OsintFinding(
                    category="subdomain",
                    value=value,
                    source="Assetfinder",
                    confidence=1.0,
                    reliability=1.0,
                    metadata={
                        "target_domain": domain,
                    },
                )
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
            "duplicates_removed": duplicates_removed,
            "filtered_out": filtered_out,
            "result_limit": result_limit,
            "limit_reached": limit_reached,
        }

        return result
