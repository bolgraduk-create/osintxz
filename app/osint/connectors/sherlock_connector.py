from __future__ import annotations

import csv
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


class SherlockConnector(BaseConnector):
    """
    Sherlock OSINT connector.

    Sherlock 0.16.x does not use --json as a result
    export option. Result export is performed through
    CSV instead.
    """

    @property
    def name(self) -> str:
        return "Sherlock"

    @property
    def description(self) -> str:
        return (
            "Username search across "
            "hundreds of websites."
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
            shutil.which("sherlock")
            is not None
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
                error="Sherlock is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            temp_path = Path(temp)

            command = [
                "sherlock",
                request.target.value,
                "--csv",
                "--print-found",
                "--no-color",
                "--no-txt",
            ]

            execution = self.runner.run(
                command=command,
                timeout=request.timeout,
                working_directory=temp_path,
            )

            if not execution.success:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        execution.stderr
                        or execution.stdout
                        or "Sherlock execution failed."
                    ),
                )

            csv_files = list(
                temp_path.glob("*.csv")
            )

            if not csv_files:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    raw_data=(
                        execution.stdout
                        if request.save_raw_output
                        else None
                    ),
                    error="Sherlock CSV report was not produced.",
                )

            findings: list[OsintFinding] = []
            parsed_rows: list[dict[str, str]] = []

            try:

                for csv_file in csv_files:

                    with csv_file.open(
                        "r",
                        encoding="utf-8-sig",
                        newline="",
                    ) as handle:

                        reader = csv.DictReader(
                            handle
                        )

                        for row in reader:

                            parsed_rows.append(
                                dict(row)
                            )

                            exists = str(
                                row.get(
                                    "exists",
                                    "",
                                )
                            ).strip().lower()

                            # Sherlock commonly reports
                            # CLAIMED for discovered profiles.
                            if (
                                "claimed"
                                not in exists
                                and exists
                                not in {
                                    "true",
                                    "yes",
                                    "1",
                                }
                            ):
                                continue

                            website = (
                                row.get("name")
                                or "Sherlock"
                            )

                            url = (
                                row.get("url_user")
                                or None
                            )

                            findings.append(
                                OsintFinding(
                                    category="account",
                                    value=request.target.value,
                                    url=url,
                                    source=website,
                                    confidence=1.0,
                                    reliability=1.0,
                                    metadata=dict(row),
                                )
                            )

            except Exception as exc:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        "Unable to parse Sherlock CSV: "
                        f"{exc}"
                    ),
                )

            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                findings=findings,
                raw_data=(
                    parsed_rows
                    if request.save_raw_output
                    else None
                ),
                execution_time=execution.execution_time,
                metadata={
                    "accounts_found": len(
                        findings
                    ),
                    "report_format": "csv",
                },
            )
