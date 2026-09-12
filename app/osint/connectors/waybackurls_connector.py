"""
Waybackurls connector.

Collects archived URLs using
Waybackurls.

Responsibilities:

- execute Waybackurls
- normalize targets to domains
- stream bounded output when a request limit exists
- parse and validate output
- deduplicate URLs
- enforce request result budget
- preserve partial output on timeout
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

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


class WaybackurlsConnector(BaseConnector):
    """
    Waybackurls connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Waybackurls"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Collect archived URLs "
            "from the Wayback Machine."
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
            "waybackurls",
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

    @staticmethod
    def _raw_line_budget(
        result_limit: int | None,
    ) -> int | None:

        if result_limit is None:
            return None

        return max(
            result_limit,
            min(
                100,
                result_limit * 4,
            ),
        )

    @classmethod
    def _target_domain(
        cls,
        request: ConnectorRequest,
    ) -> str:

        raw_value = str(
            request.target.value
        ).strip()

        if (
            request.target.target_type
            == OsintTargetType.URL
        ):

            parsed = urlsplit(
                raw_value,
            )

            if not parsed.hostname:
                parsed = urlsplit(
                    f"https://{raw_value}",
                )

            return cls._normalize_domain(
                parsed.hostname
                or ""
            )

        return cls._normalize_domain(
            raw_value,
        )

    @classmethod
    def _url_in_scope(
        cls,
        url: str,
        domain: str,
        include_related: bool,
    ) -> bool:

        try:

            parsed = urlsplit(
                url,
            )

        except ValueError:

            return False

        if (
            parsed.scheme.lower()
            not in {
                "http",
                "https",
            }
            or not parsed.hostname
        ):

            return False

        hostname = (
            cls._normalize_domain(
                parsed.hostname,
            )
        )

        if include_related:

            return (
                hostname == domain
                or hostname.endswith(
                    f".{domain}"
                )
            )

        return (
            hostname == domain
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
                error="Waybackurls is not installed.",
            )

        domain = self._target_domain(
            request,
        )

        if not domain:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error="Invalid domain/URL target.",
            )

        result_limit = self._result_limit(
            request,
        )

        if result_limit == 0:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                metadata={
                    "urls_found": 0,
                    "result_limit": 0,
                    "limit_reached": True,
                    "target_domain": domain,
                },
            )

        raw_line_budget = (
            self._raw_line_budget(
                result_limit,
            )
        )

        execution = self.runner.run(
            command=build_tool_command(
                "waybackurls",
            ),
            stdin=domain,
            timeout=request.timeout,
            stdout_line_limit=raw_line_budget,
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
                    or "Waybackurls execution failed."
                ),
            )

        findings: list[
            OsintFinding
        ] = []

        seen_urls: set[str] = set()

        duplicates_removed = 0
        invalid_or_out_of_scope = 0

        for line in execution.stdout.splitlines():

            url = line.strip()

            if not url:
                continue

            if not self._url_in_scope(
                url,
                domain,
                request.include_related,
            ):

                invalid_or_out_of_scope += 1
                continue

            if url in seen_urls:
                duplicates_removed += 1
                continue

            if (
                result_limit is not None
                and len(findings) >= result_limit
            ):
                break

            seen_urls.add(
                url,
            )

            findings.append(
                OsintFinding(
                    category="archived_url",
                    value=url,
                    source="Waybackurls",
                    url=url,
                    confidence=1.0,
                    reliability=1.0,
                    metadata={
                        "target_domain": domain,
                    },
                )
            )

        timed_out = (
            execution.return_code == -1
        )

        limit_reached = (
            result_limit is not None
            and len(findings) >= result_limit
        )

        if timed_out and findings:

            status = (
                ResultStatus.PARTIAL
            )

            error = (
                execution.stderr
                or "Waybackurls timed out after returning partial results."
            )

        elif timed_out:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "Waybackurls timed out."
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
                or "Waybackurls returned partial output."
            )

        else:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "Waybackurls execution failed."
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
            "urls_found": result.total_findings,
            "duplicates_removed": duplicates_removed,
            "invalid_or_out_of_scope": invalid_or_out_of_scope,
            "timed_out": timed_out,
            "stream_stopped_early": execution.stopped_early,
            "target_domain": domain,
            "result_limit": result_limit,
            "raw_line_budget": raw_line_budget,
            "limit_reached": limit_reached,
        }

        return result
