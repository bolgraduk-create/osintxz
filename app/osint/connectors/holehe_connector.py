from __future__ import annotations

import csv
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


class HoleheConnector(BaseConnector):
    """
    Holehe email-registration connector.

    Current Holehe CLI does not provide JSON output.

    Production integration uses CSV:

        holehe <email>
            --only-used
            --no-color
            --no-clear
            -C

    Note:
    some Holehe versions may return a non-zero process
    code even when the scan finishes and the CSV report
    is successfully produced.

    Therefore report existence and parseability are the
    authoritative success criteria.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Holehe"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Searches account registrations "
            "using an email address."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.EMAIL,
        }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return (
            shutil.which(
                "holehe"
            )
            is not None
        )

    @staticmethod
    def _as_bool(
        value: Any,
    ) -> bool | None:

        if isinstance(
            value,
            bool,
        ):
            return value

        if isinstance(
            value,
            int,
        ):
            return bool(
                value
            )

        if isinstance(
            value,
            str,
        ):

            normalized = (
                value
                .strip()
                .lower()
            )

            if normalized in {
                "true",
                "1",
                "yes",
            }:
                return True

            if normalized in {
                "false",
                "0",
                "no",
            }:
                return False

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
                error="Holehe is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            temp_path = Path(
                temp
            )

            command = [
                "holehe",
                request.target.value,
                "--only-used",
                "--no-color",
                "--no-clear",
                "-C",
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

            # ==================================================
            # Discover report
            # ==================================================

            csv_files = [
                path
                for path in temp_path.rglob(
                    "*.csv"
                )
                if path.is_file()
            ]

            if not csv_files:

                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=(
                        execution.execution_time
                    ),
                    error=(
                        execution.stderr
                        or execution.stdout
                        or (
                            "Holehe did not produce "
                            "a CSV report."
                        )
                    ),
                    metadata={
                        "tool_return_code": (
                            execution.return_code
                        ),
                    },
                )

            report_file = max(
                csv_files,
                key=lambda path: (
                    path.stat().st_mtime
                ),
            )

            # ==================================================
            # Parse CSV
            # ==================================================

            try:

                with report_file.open(
                    "r",
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                ) as handle:

                    reader = csv.DictReader(
                        handle
                    )

                    rows = [
                        dict(row)
                        for row in reader
                    ]

            except Exception as exc:

                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=(
                        execution.execution_time
                    ),
                    error=(
                        "Unable to parse Holehe CSV: "
                        f"{exc}"
                    ),
                    metadata={
                        "tool_return_code": (
                            execution.return_code
                        ),
                        "report_file": (
                            report_file.name
                        ),
                    },
                )

            # ==================================================
            # Findings
            # ==================================================

            result = OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                execution_time=(
                    execution.execution_time
                ),
                raw_data=(
                    rows
                    if request.save_raw_output
                    else None
                ),
            )

            rate_limited = 0
            checked = 0

            for row in rows:

                checked += 1

                exists = self._as_bool(
                    row.get(
                        "exists"
                    )
                )

                rate_limit = self._as_bool(
                    row.get(
                        "rateLimit"
                    )
                )

                if rate_limit is True:
                    rate_limited += 1

                if exists is not True:
                    continue

                domain = (
                    row.get(
                        "domain"
                    )
                    or ""
                ).strip()

                source = (
                    row.get(
                        "name"
                    )
                    or domain
                    or "Holehe"
                )

                url = None

                if domain:

                    if domain.startswith(
                        (
                            "http://",
                            "https://",
                        )
                    ):
                        url = domain

                    else:
                        url = (
                            f"https://{domain}"
                        )

                result.add_finding(
                    OsintFinding(
                        category="account",
                        value=(
                            request.target.value
                        ),
                        source=source,
                        url=url,
                        confidence=1.0,
                        reliability=1.0,
                        metadata={
                            **row,
                            "exists": exists,
                            "rate_limited": (
                                rate_limit
                            ),
                        },
                    )
                )

            result.metadata = {
                "accounts_found": (
                    result.total_findings
                ),
                "sites_checked": checked,
                "rate_limited": (
                    rate_limited
                ),
                "report_format": "csv",
                "report_file": (
                    report_file.name
                ),
                "tool_return_code": (
                    execution.return_code
                ),
                "tool_report_produced": True,
            }

            return result