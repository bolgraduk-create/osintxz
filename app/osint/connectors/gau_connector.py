"""
GAU connector.

Collects historical URLs using
GetAllURLs (gau).

Responsibilities:

- execute gau
- normalize URL targets to domains
- use a fast bounded provider strategy when a result budget exists
- parse and validate output
- deduplicate discovered URLs
- enforce request result budget
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
    PROJECT_ROOT,
    build_tool_command,
    tool_available,
)


class GauConnector(BaseConnector):
    """
    GAU connector.

    When ``ConnectorRequest.limit`` is set, the connector intentionally
    uses the low-latency OTX + URLScan provider pair. Wayback and Common
    Crawl are represented elsewhere in the OSINT subsystem and should not
    block a bounded recursive request.

    Unbounded/manual requests preserve GAU's normal all-provider behaviour.
    """

    _FAST_PROVIDERS = (
        "urlscan,otx"
    )

    _CONFIG_PATH = (
        PROJECT_ROOT
        / "tools"
        / "osint"
        / "config"
        / "gau.toml"
    )

    @property
    def name(
        self,
    ) -> str:

        return "GAU"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Collect historical URLs "
            "using GetAllURLs."
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
            "gau",
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

    @staticmethod
    def _provider_timeout(
        request_timeout: int,
        bounded: bool,
    ) -> int:

        timeout = max(
            1,
            int(request_timeout),
        )

        if bounded:

            return max(
                2,
                min(
                    5,
                    timeout,
                ),
            )

        return max(
            5,
            min(
                30,
                timeout // 4,
            ),
        )

    @classmethod
    def _url_in_scope(
        cls,
        url: str,
        domain: str,
        include_related: bool,
    ) -> tuple[
        bool,
        str | None,
    ]:

        try:
            parsed = urlsplit(
                url,
            )
        except ValueError:
            return (
                False,
                None,
            )

        if (
            parsed.scheme.lower()
            not in {
                "http",
                "https",
            }
            or not parsed.hostname
        ):
            return (
                False,
                None,
            )

        hostname = (
            cls._normalize_domain(
                parsed.hostname,
            )
        )

        if include_related:

            in_scope = (
                hostname == domain
                or hostname.endswith(
                    f".{domain}"
                )
            )

        else:

            in_scope = (
                hostname == domain
            )

        return (
            in_scope,
            hostname,
        )

    @staticmethod
    def _url_dedupe_key(
        url: str,
    ) -> tuple[
        str,
        str,
        int | None,
        str,
        str,
    ] | None:

        try:

            parsed = urlsplit(
                url,
            )

            if (
                not parsed.hostname
                or parsed.scheme.lower()
                not in {
                    "http",
                    "https",
                }
            ):
                return None

            return (
                parsed.scheme.lower(),
                parsed.hostname.lower(),
                parsed.port,
                parsed.path,
                parsed.query,
            )

        except ValueError:

            return None

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
                error="GAU is not installed.",
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
                    "provider_strategy": "bounded_fast",
                    "providers_used": self._FAST_PROVIDERS,
                },
            )

        bounded = (
            result_limit is not None
        )

        provider_timeout = (
            self._provider_timeout(
                request.timeout,
                bounded,
            )
        )

        arguments = [
            "--config",
            str(self._CONFIG_PATH),
            "--threads",
            "2" if bounded else "5",
            "--timeout",
            str(provider_timeout),
            "--retries",
            "0" if bounded else "1",
        ]

        if bounded:

            arguments.extend(
                [
                    "--providers",
                    self._FAST_PROVIDERS,
                ]
            )

        if request.include_related:

            arguments.append(
                "--subs",
            )

        arguments.append(
            domain,
        )

        raw_line_budget = (
            self._raw_line_budget(
                result_limit,
            )
        )

        execution = self.runner.run(
            command=build_tool_command(
                "gau",
                *arguments,
            ),
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
                    or "GAU execution failed."
                ),
            )

        findings: list[
            OsintFinding
        ] = []

        seen_urls: set[
            tuple[
                str,
                str,
                int | None,
                str,
                str,
            ]
        ] = set()

        filtered_out = 0
        duplicates_removed = 0
        invalid_urls = 0

        for line in execution.stdout.splitlines():

            url = line.strip()

            if not url:
                continue

            key = self._url_dedupe_key(
                url,
            )

            if key is None:
                invalid_urls += 1
                continue

            in_scope, hostname = (
                self._url_in_scope(
                    url,
                    domain,
                    request.include_related,
                )
            )

            if not in_scope:
                filtered_out += 1
                continue

            if key in seen_urls:
                duplicates_removed += 1
                continue

            if (
                result_limit is not None
                and len(findings) >= result_limit
            ):
                break

            seen_urls.add(
                key,
            )

            findings.append(
                OsintFinding(
                    category="historical_url",
                    value=url,
                    url=url,
                    source="GAU",
                    confidence=1.0,
                    reliability=1.0,
                    metadata={
                        "hostname": hostname,
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
                or "GAU timed out after returning partial results."
            )

        elif timed_out:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "GAU timed out."
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
                or "GAU returned partial output."
            )

        else:

            status = (
                ResultStatus.FAILED
            )

            error = (
                execution.stderr
                or "GAU execution failed."
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
            "filtered_out": filtered_out,
            "invalid_urls": invalid_urls,
            "timed_out": timed_out,
            "stream_stopped_early": execution.stopped_early,
            "target_domain": domain,
            "provider_timeout": provider_timeout,
            "provider_strategy": (
                "bounded_fast"
                if bounded
                else "unbounded_all"
            ),
            "providers_used": (
                self._FAST_PROVIDERS
                if bounded
                else "gau_default_all"
            ),
            "result_limit": result_limit,
            "raw_line_budget": raw_line_budget,
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
