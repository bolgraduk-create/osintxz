from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class MaigretConnector(BaseConnector):
    """Bounded Maigret username scan with partial-report recovery."""

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
            # Newer Maigret status objects may serialize an is_found flag.
            for key in ("is_found", "found", "claimed"):
                if status.get(key) is True:
                    return True
        return bool(info.get("url_user") or info.get("url") or info.get("profile_url"))

    @staticmethod
    def _process_budget(request_timeout: int) -> int:
        return max(70, min(95, int(request_timeout or 15) * 4))

    @staticmethod
    def _site_timeout(request_timeout: int) -> int:
        return max(3, min(6, max(3, int(request_timeout or 15) // 3)))

    @staticmethod
    def _owner_url(username: str, url: str) -> bool:
        wanted = str(username or "").strip().lstrip("@").casefold()
        try:
            parsed = urlsplit(str(url or ""))
        except ValueError:
            return False
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments and segments[0].lstrip("@").casefold() == wanted:
            return True
        if not segments:
            parts = (parsed.hostname or "").casefold().split(".")
            return bool(parts and parts[0] == wanted)
        return False

    @classmethod
    def _stdout_findings(cls, stdout: str, username: str) -> list[OsintFinding]:
        out: list[OsintFinding] = []
        seen: set[str] = set()
        for line in str(stdout or "").splitlines():
            for url in re.findall(r"https?://[^\s\]\[()<>\"']+", line):
                url = url.rstrip(".,;:")
                if url in seen or not cls._owner_url(username, url):
                    continue
                seen.add(url)
                out.append(
                    OsintFinding(
                        category="account",
                        value=username,
                        url=url,
                        source="Maigret",
                        confidence=0.91,
                        reliability=0.86,
                        metadata={
                            "registration_confirmed": True,
                            "partial_stdout_recovery": True,
                            "public_data_only": True,
                        },
                    )
                )
        return out

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

        username = request.target.value.strip()
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            command = [
                executable,
                username,
                "--json", "simple",
                "--folderoutput", str(temp_path),
                "--no-color", "--no-progressbar", "--no-autoupdate",
                "--top-sites", "300",
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
            seen_urls: set[str] = set()
            if json_files:
                report_file = max(json_files, key=lambda path: path.stat().st_mtime)
                try:
                    data = json.loads(report_file.read_text(encoding="utf-8"))
                    for website, info in self._iter_site_records(data):
                        if not self._is_found(info):
                            continue
                        url = info.get("url_user") or info.get("url") or info.get("profile_url")
                        if url:
                            seen_urls.add(str(url))
                        findings.append(
                            OsintFinding(
                                category="account",
                                value=username,
                                url=url,
                                source=str(website),
                                confidence=0.96,
                                reliability=0.92,
                                metadata={**info, "registration_confirmed": True, "public_data_only": True},
                            )
                        )
                except Exception as exc:
                    parse_error = f"Unable to parse Maigret JSON: {exc}"

            for finding in self._stdout_findings(execution.stdout, username):
                url = str(finding.url or "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    findings.append(finding)

        timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
        if findings or data is not None:
            status = ResultStatus.SUCCESS if execution.success and not parse_error else ResultStatus.PARTIAL
            return OsintResult(
                connector=self.name,
                status=status,
                findings=findings,
                raw_data=data if request.save_raw_output else None,
                execution_time=execution.execution_time,
                error=parse_error or ("Maigret process budget reached; partial findings retained." if timed_out else None),
                metadata={
                    "accounts_found": len(findings),
                    "report_format": "json-simple+stdout-recovery",
                    "fast_pass": True,
                    "top_sites": 300,
                    "timed_out": timed_out,
                    "partial_results_retained": status is ResultStatus.PARTIAL,
                    "site_timeout_seconds": self._site_timeout(request.timeout),
                    "process_budget_seconds": self._process_budget(request.timeout),
                },
            )

        if not execution.success:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL if timed_out else ResultStatus.FAILED,
                execution_time=execution.execution_time,
                error=execution.stderr or execution.stdout or "Maigret execution failed.",
                metadata={"fast_pass": True, "timed_out": timed_out, "repairable": True},
            )
        return OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            findings=[],
            execution_time=execution.execution_time,
            metadata={"fast_pass": True, "accounts_found": 0, "top_sites": 300},
        )
