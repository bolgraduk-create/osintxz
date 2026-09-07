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

    GHunt also requires a UTF-8 child process
    environment on Windows to avoid console encoding
    failures.
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

    def is_available(self) -> bool:
        return (
            shutil.which(
                "ghunt"
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
                error="GHunt is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = (
                Path(temp)
                / "result.json"
            )

            command = [
                "ghunt",
                "email",
                request.target.value,
                "--json",
                str(output),
            ]

            execution = self.runner.run(
                command=command,
                timeout=request.timeout,
                env={
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
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

            # GHunt returns a structured investigation
            # object rather than a flat account list.
            #
            # Preserve the complete JSON in metadata,
            # but create one finding representing the
            # Google account investigation.

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

            result.metadata = {
                "records_found": (
                    result.total_findings
                ),
                "report_format": "json",
            }

            return result
