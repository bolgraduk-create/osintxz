from __future__ import annotations

import csv
import shutil
import sys
import tempfile
from pathlib import Path

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class SherlockConnector(BaseConnector):
    """Bounded Sherlock username search with partial-result recovery."""

    name = "Sherlock"
    description = "Username search across hundreds of websites."
    supported_targets = {OsintTargetType.USERNAME}

    def __init__(self) -> None:
        self.runner = ToolRunner()

    @classmethod
    def executable(cls) -> str | None:
        scripts = Path(sys.executable).resolve().parent
        for candidate in (scripts / "sherlock.exe", scripts / "sherlock"):
            if candidate.is_file():
                return str(candidate)
        return shutil.which("sherlock")

    def is_available(self) -> bool:
        return self.executable() is not None

    @staticmethod
    def _process_budget(request_timeout: int) -> int:
        # The unified worker historically gives connectors ~15s. Sherlock
        # checks hundreds of hosts, so give the subprocess a bounded but useful
        # fast-pass budget while keeping each individual site short.
        return max(35, min(75, int(request_timeout or 15) * 3))

    @staticmethod
    def _site_timeout(request_timeout: int) -> int:
        return max(3, min(7, max(3, int(request_timeout or 15) // 3)))

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if not self.validate_target(request):
            return OsintResult(connector=self.name, status=ResultStatus.NOT_SUPPORTED, error="Unsupported target.")

        executable = self.executable()
        if not executable:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="Sherlock is not installed in the project Python environment.",
                metadata={
                    "install_hint": r".\.venv\Scripts\python.exe -m pip install --upgrade sherlock-project",
                    "repairable": True,
                },
            )

        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            command = [
                executable,
                request.target.value,
                "--csv",
                "--print-found",
                "--no-color",
                "--timeout",
                str(self._site_timeout(request.timeout)),
            ]
            execution = self.runner.run(
                command=command,
                timeout=self._process_budget(request.timeout),
                working_directory=temp_path,
            )

            csv_files = list(temp_path.glob("*.csv"))
            findings: list[OsintFinding] = []
            parsed_rows: list[dict[str, str]] = []
            parse_error = ""
            try:
                for csv_file in csv_files:
                    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
                        for row in csv.DictReader(handle):
                            item = dict(row)
                            parsed_rows.append(item)
                            exists = str(item.get("exists", "")).strip().lower()
                            if "claimed" not in exists and exists not in {"true", "yes", "1", "found"}:
                                continue
                            website = item.get("name") or item.get("site") or "Sherlock"
                            url = item.get("url_user") or item.get("url") or None
                            findings.append(
                                OsintFinding(
                                    category="account",
                                    value=request.target.value,
                                    url=url,
                                    source=str(website),
                                    confidence=0.96,
                                    reliability=0.92,
                                    metadata=item,
                                )
                            )
            except Exception as exc:
                parse_error = f"Unable to parse Sherlock CSV: {exc}"

            timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
            if findings or parsed_rows:
                status = ResultStatus.SUCCESS if execution.success and not parse_error else ResultStatus.PARTIAL
                error = parse_error or ("Sherlock fast-pass reached its process budget; partial findings retained." if timed_out else (execution.stderr or ""))
                return OsintResult(
                    connector=self.name,
                    status=status,
                    findings=findings,
                    raw_data=parsed_rows if request.save_raw_output else None,
                    execution_time=execution.execution_time,
                    error=error or None,
                    metadata={
                        "accounts_found": len(findings),
                        "rows_parsed": len(parsed_rows),
                        "report_format": "csv",
                        "fast_pass": True,
                        "timed_out": timed_out,
                        "partial_results_retained": status is ResultStatus.PARTIAL,
                        "site_timeout_seconds": self._site_timeout(request.timeout),
                        "process_budget_seconds": self._process_budget(request.timeout),
                    },
                )

            if not execution.success:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=execution.stderr or execution.stdout or "Sherlock execution failed.",
                    metadata={
                        "fast_pass": True,
                        "timed_out": timed_out,
                        "repairable": True,
                    },
                )

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                execution_time=execution.execution_time,
                error=parse_error or "Sherlock completed but produced no CSV report.",
                metadata={"fast_pass": True, "repairable": True},
            )
