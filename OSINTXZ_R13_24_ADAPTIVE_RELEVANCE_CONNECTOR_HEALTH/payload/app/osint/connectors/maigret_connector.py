from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class MaigretConnector(BaseConnector):
    """Bounded Maigret fast pass with partial-report recovery."""

    name = "Maigret"
    description = "Advanced username OSINT search."
    supported_targets = {OsintTargetType.USERNAME}

    def __init__(self) -> None:
        self.runner = ToolRunner()

    @classmethod
    def executable(cls) -> str | None:
        scripts = Path(sys.executable).resolve().parent
        for candidate in (scripts / "maigret.exe", scripts / "maigret"):
            if candidate.is_file():
                return str(candidate)
        return shutil.which("maigret")

    def is_available(self) -> bool:
        return self.executable() is not None

    @staticmethod
    def _iter_site_records(data: Any):
        if isinstance(data, dict):
            for wrapper_key in ("results", "sites", "accounts"):
                wrapped = data.get(wrapper_key)
                if isinstance(wrapped, dict):
                    data = wrapped
                    break
            if isinstance(data, dict):
                for website, info in data.items():
                    if isinstance(info, dict):
                        yield website, info
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item.get("site") or item.get("name") or item.get("service") or "Maigret", item

    @staticmethod
    def _is_found(info: dict[str, Any]) -> bool:
        status = info.get("status")
        if isinstance(status, bool):
            return status
        if isinstance(status, str):
            return status.strip().lower() in {"claimed", "found", "exists", "true", "success"}
        if isinstance(status, dict):
            value = status.get("status") or status.get("value")
            if isinstance(value, str):
                return value.strip().lower() in {"claimed", "found", "exists", "true", "success"}
        return bool(info.get("url_user") or info.get("url") or info.get("profile_url"))

    @staticmethod
    def _process_budget(request_timeout: int) -> int:
        return max(45, min(90, int(request_timeout or 15) * 4))

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
                error="Maigret is not installed in the project Python environment.",
                metadata={
                    "install_hint": r".\.venv\Scripts\python.exe -m pip install --upgrade maigret",
                    "repairable": True,
                },
            )

        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            command = [
                executable,
                request.target.value,
                "--json", "simple",
                "--folderoutput", str(temp_path),
                "--no-color", "--no-progressbar", "--no-autoupdate",
                "--top-sites", "140",
                "--timeout", str(self._site_timeout(request.timeout)),
                "--retries", "0",
                "--no-recursion",
                "--no-extracting",
            ]
            execution = self.runner.run(
                command=command,
                timeout=self._process_budget(request.timeout),
                working_directory=temp_path,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            json_files = [path for path in temp_path.rglob("*.json") if path.is_file()]
            findings: list[OsintFinding] = []
            data: Any = None
            parse_error = ""
            if json_files:
                report_file = max(json_files, key=lambda path: path.stat().st_mtime)
                try:
                    data = json.loads(report_file.read_text(encoding="utf-8"))
                    for website, info in self._iter_site_records(data):
                        if not self._is_found(info):
                            continue
                        url = info.get("url_user") or info.get("url") or info.get("profile_url")
                        findings.append(
                            OsintFinding(
                                category="account",
                                value=request.target.value,
                                url=url,
                                source=str(website),
                                confidence=0.96,
                                reliability=0.92,
                                metadata=info,
                            )
                        )
                except Exception as exc:
                    parse_error = f"Unable to parse Maigret JSON: {exc}"

            timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
            if findings or data is not None:
                status = ResultStatus.SUCCESS if execution.success and not parse_error else ResultStatus.PARTIAL
                error = parse_error or ("Maigret fast-pass reached its process budget; partial findings retained." if timed_out else (execution.stderr or ""))
                return OsintResult(
                    connector=self.name,
                    status=status,
                    findings=findings,
                    raw_data=data if request.save_raw_output else None,
                    execution_time=execution.execution_time,
                    error=error or None,
                    metadata={
                        "accounts_found": len(findings),
                        "report_format": "json-simple",
                        "fast_pass": True,
                        "top_sites": 140,
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
                    error=execution.stderr or execution.stdout or "Maigret execution failed.",
                    metadata={"fast_pass": True, "timed_out": timed_out, "repairable": True},
                )
            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                execution_time=execution.execution_time,
                raw_data=execution.stdout if request.save_raw_output else None,
                error="Maigret completed but produced no JSON report.",
                metadata={"fast_pass": True, "repairable": True},
            )
