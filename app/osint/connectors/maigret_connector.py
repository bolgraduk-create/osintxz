from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

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


class MaigretConnector(BaseConnector):
    """
    Maigret username connector.

    Maigret 0.6.5 uses:

        --json simple

    to select the JSON report type.

    The report itself is created inside the working
    directory.
    """

    @property
    def name(self) -> str:
        return "Maigret"

    @property
    def description(self) -> str:
        return (
            "Advanced username "
            "OSINT search."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.USERNAME,
        }

    def __init__(self) -> None:
        self.runner = ToolRunner()

    def is_available(self) -> bool:
        return (
            shutil.which("maigret")
            is not None
        )

    @staticmethod
    def _iter_site_records(
        data: Any,
    ):

        if isinstance(data, dict):

            # Some report versions wrap results.
            for wrapper_key in (
                "results",
                "sites",
                "accounts",
            ):

                wrapped = data.get(
                    wrapper_key
                )

                if isinstance(
                    wrapped,
                    dict,
                ):
                    data = wrapped
                    break

            if isinstance(data, dict):

                for website, info in (
                    data.items()
                ):

                    if isinstance(
                        info,
                        dict,
                    ):
                        yield website, info

        elif isinstance(data, list):

            for item in data:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                website = (
                    item.get("site")
                    or item.get("name")
                    or item.get("service")
                    or "Maigret"
                )

                yield website, item

    @staticmethod
    def _is_found(
        info: dict[str, Any],
    ) -> bool:

        status = info.get(
            "status"
        )

        if isinstance(status, bool):
            return status

        if isinstance(status, str):

            lowered = (
                status
                .strip()
                .lower()
            )

            return lowered in {
                "claimed",
                "found",
                "exists",
                "true",
                "success",
            }

        if isinstance(status, dict):

            value = (
                status.get("status")
                or status.get("value")
            )

            if isinstance(value, str):

                return (
                    value
                    .strip()
                    .lower()
                    in {
                        "claimed",
                        "found",
                        "exists",
                        "true",
                        "success",
                    }
                )

        # Some simple reports only contain
        # claimed accounts.
        return bool(
            info.get("url_user")
            or info.get("url")
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:

        if not self.validate_target(
            request,
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
                error="Maigret is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            temp_path = Path(temp)

            command = [
                "maigret",
                request.target.value,
                "--json",
                "simple",
                "--folderoutput",
                str(temp_path),
                "--no-color",
                "--no-progressbar",
                "--no-autoupdate",
            ]

            execution = self.runner.run(
                command=command,
                timeout=request.timeout,
                working_directory=temp_path,
                env={
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
            )

            if not execution.success:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        execution.stderr
                        or execution.stdout
                        or "Maigret execution failed."
                    ),
                )

            json_files = [
                path
                for path in temp_path.rglob("*.json")
                if path.is_file()
            ]

            if not json_files:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    raw_data=(
                        execution.stdout
                        if request.save_raw_output
                        else None
                    ),
                    error="Maigret JSON report was not produced.",
                )

            report_file = max(
                json_files,
                key=lambda path: (
                    path.stat().st_mtime
                ),
            )

            try:

                data = json.loads(
                    report_file.read_text(
                        encoding="utf-8",
                    )
                )

            except Exception as exc:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        "Unable to parse Maigret JSON: "
                        f"{exc}"
                    ),
                )

            findings: list[
                OsintFinding
            ] = []

            for website, info in (
                self._iter_site_records(
                    data
                )
            ):

                if not self._is_found(
                    info
                ):
                    continue

                url = (
                    info.get("url_user")
                    or info.get("url")
                    or info.get(
                        "profile_url"
                    )
                )

                findings.append(
                    OsintFinding(
                        category="account",
                        value=request.target.value,
                        url=url,
                        source=str(
                            website
                        ),
                        confidence=1.0,
                        reliability=1.0,
                        metadata=info,
                    )
                )

            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                findings=findings,
                raw_data=(
                    data
                    if request.save_raw_output
                    else None
                ),
                execution_time=execution.execution_time,
                metadata={
                    "accounts_found": len(
                        findings
                    ),
                    "report_format": (
                        "json-simple"
                    ),
                },
            )
