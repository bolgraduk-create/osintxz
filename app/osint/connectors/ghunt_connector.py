from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

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


class GHuntConnector(BaseConnector):
    """
    GHunt connector.

    GHunt 2.3.x email syntax:

        ghunt email <email> --json <output-file>

    GHunt requires a UTF-8 child process environment on Windows.
    The same environment is used for the lightweight CLI health-check
    so a cp1251 console cannot make an otherwise valid install appear
    available and then fail immediately.
    """

    @property
    def name(self) -> str:
        return "GHunt"

    @property
    def description(self) -> str:
        return (
            "Searches Google account information "
            "using an email address."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.EMAIL,
        }

    def __init__(self) -> None:
        self.runner = ToolRunner()

    @staticmethod
    def _runtime_env() -> dict[str, str]:

        return {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }

    @staticmethod
    def _fatal_runtime_error(
        text: str,
    ) -> bool:

        lowered = text.casefold()

        return any(
            marker in lowered
            for marker in (
                "traceback (most recent call last)",
                "modulenotfounderror:",
                "importerror:",
                "unicodeencodeerror:",
            )
        )

    def _resolve_executable(
        self,
    ) -> str | None:

        return shutil.which(
            "ghunt",
        )

    def _health_check(
        self,
    ) -> tuple[
        bool,
        str | None,
    ]:

        executable = (
            self._resolve_executable()
        )

        if executable is None:

            return (
                False,
                "GHunt is not installed.",
            )

        execution = self.runner.run(
            command=[
                executable,
                "--help",
            ],
            timeout=8,
            env=self._runtime_env(),
        )

        output = "\n".join(
            part
            for part in (
                execution.stdout,
                execution.stderr,
            )
            if part
        )

        if self._fatal_runtime_error(
            output,
        ):

            return (
                False,
                (
                    "GHunt CLI failed its runtime "
                    "health-check."
                ),
            )

        normalized = (
            output.casefold()
        )

        recognizable = (
            "ghunt" in normalized
        )

        acceptable_exit = (
            execution.return_code
            in {
                0,
                1,
                2,
            }
        )

        if (
            recognizable
            and acceptable_exit
        ):

            return (
                True,
                None,
            )

        return (
            False,
            (
                execution.stderr
                or execution.stdout
                or "GHunt CLI health-check failed."
            )[:2000],
        )

    def is_available(self) -> bool:

        healthy, _ = (
            self._health_check()
        )

        return healthy

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

        healthy, health_error = (
            self._health_check()
        )

        if not healthy:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error=(
                    health_error
                    or "GHunt is not available."
                ),
                metadata={
                    "runtime_health": "failed",
                },
            )

        result_limit = (
            self._result_limit(
                request,
            )
        )

        if result_limit == 0:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                metadata={
                    "records_found": 0,
                    "report_format": "json",
                    "result_limit": 0,
                    "limit_reached": True,
                    "runtime_health": "healthy",
                },
            )

        executable = (
            self._resolve_executable()
        )

        if executable is None:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="GHunt is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = (
                Path(temp)
                / "result.json"
            )

            command = [
                executable,
                "email",
                request.target.value,
                "--json",
                str(output),
            ]

            execution = self.runner.run(
                command=command,
                timeout=request.timeout,
                env=self._runtime_env(),
            )

            if not execution.success:

                error_text = "\n".join(
                    part
                    for part in (
                        execution.stderr,
                        execution.stdout,
                    )
                    if part
                )

                normalized_error = (
                    error_text
                    .casefold()
                )

                auth_markers = (
                    "ghuntinvalidsession",
                    "no stored session found",
                    "please generate a new session",
                    "ghunt login",
                )

                if any(
                    marker in normalized_error
                    for marker in auth_markers
                ):
                    return OsintResult(
                        connector=self.name,
                        status=ResultStatus.NOT_AVAILABLE,
                        execution_time=execution.execution_time,
                        error=(
                            "GHunt requires an authenticated "
                            "Google session. Run 'ghunt login' "
                            "before using this connector."
                        ),
                        metadata={
                            "authentication_required": True,
                            "reason": "missing_ghunt_session",
                            "runtime_health": "healthy",
                        },
                    )

                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        error_text
                        or "GHunt execution failed."
                    ),
                    metadata={
                        "runtime_health": "healthy",
                    },
                )

            if not output.exists():
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    raw_data=(
                        execution.stdout
                        if request.save_raw_output
                        else None
                    ),
                    error="GHunt JSON report was not produced.",
                    metadata={
                        "runtime_health": "healthy",
                    },
                )

            try:

                data = json.loads(
                    output.read_text(
                        encoding="utf-8",
                    )
                )

            except Exception as exc:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        "Unable to parse GHunt JSON: "
                        f"{exc}"
                    ),
                    metadata={
                        "runtime_health": "healthy",
                    },
                )

            result = OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                execution_time=execution.execution_time,
                raw_data=(
                    data
                    if request.save_raw_output
                    else None
                ),
            )

            if isinstance(data, dict):

                result.add_finding(
                    OsintFinding(
                        category="google_account",
                        value=request.target.value,
                        source="GHunt",
                        confidence=1.0,
                        reliability=1.0,
                        metadata=data,
                    )
                )

            limit_reached = (
                result_limit is not None
                and result.total_findings
                >= result_limit
            )

            if (
                result_limit is not None
                and result.total_findings
                > result_limit
            ):

                result.findings = (
                    result.findings[
                        :result_limit
                    ]
                )

            result.metadata = {
                "records_found": (
                    result.total_findings
                ),
                "report_format": "json",
                "result_limit": result_limit,
                "limit_reached": limit_reached,
                "runtime_health": "healthy",
            }

            return result
