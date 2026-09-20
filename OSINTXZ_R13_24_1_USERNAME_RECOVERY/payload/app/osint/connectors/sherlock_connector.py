from __future__ import annotations

import csv
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class SherlockConnector(BaseConnector):
    """Bounded Sherlock username search with timeout-result recovery.

    R13.24.1 deliberately uses Sherlock's bundled local site database so a
    username scan does not spend part of its process budget fetching data.json.
    CSV is preferred, while already printed claimed URLs are recovered from
    partial stdout when the process budget is reached before CSV finalisation.
    """

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
        return max(60, min(80, int(request_timeout or 15) * 4))

    @staticmethod
    def _site_timeout(request_timeout: int) -> int:
        return max(3, min(5, max(3, int(request_timeout or 15) // 4)))

    @staticmethod
    def _owner_url(username: str, url: str) -> bool:
        wanted = str(username or "").strip().lstrip("@").casefold()
        if not wanted or not str(url or "").startswith(("http://", "https://")):
            return False
        try:
            parsed = urlsplit(str(url))
        except ValueError:
            return False
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            # Some account systems use a username subdomain.
            host_parts = (parsed.hostname or "").casefold().split(".")
            return bool(host_parts and host_parts[0] == wanted)
        if segments[0].lstrip("@").casefold() == wanted:
            return True
        namespaces = {"user", "users", "u", "profile", "profiles", "people", "member", "members", "channel", "c"}
        return bool(
            len(segments) >= 2
            and segments[0].casefold() in namespaces
            and segments[1].lstrip("@").casefold() == wanted
        )

    @classmethod
    def _stdout_findings(cls, stdout: str, username: str) -> list[OsintFinding]:
        findings: list[OsintFinding] = []
        seen: set[str] = set()
        for line in str(stdout or "").splitlines():
            urls = re.findall(r"https?://[^\s\]\[()<>\"']+", line)
            for url in urls:
                url = url.rstrip(".,;:")
                if url in seen or not cls._owner_url(username, url):
                    continue
                seen.add(url)
                prefix = line.split(url, 1)[0]
                source = re.sub(r"^[^A-Za-z0-9]+|[:\s]+$", "", prefix).strip()
                if len(source) > 80:
                    source = source[-80:]
                findings.append(
                    OsintFinding(
                        category="account",
                        value=username,
                        url=url,
                        source=source or "Sherlock",
                        confidence=0.94,
                        reliability=0.90,
                        metadata={
                            "registration_confirmed": True,
                            "partial_stdout_recovery": True,
                            "public_data_only": True,
                        },
                    )
                )
        return findings

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

        username = request.target.value.strip()
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            command = [
                executable,
                username,
                "--local",
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
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )

            findings: list[OsintFinding] = []
            parsed_rows: list[dict[str, str]] = []
            seen_urls: set[str] = set()
            parse_error = ""
            try:
                for csv_file in temp_path.glob("*.csv"):
                    with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
                        for row in csv.DictReader(handle):
                            item = dict(row)
                            parsed_rows.append(item)
                            exists = str(item.get("exists", "")).strip().casefold()
                            if "claimed" not in exists and exists not in {"true", "yes", "1", "found"}:
                                continue
                            url = str(item.get("url_user") or item.get("url") or "").strip()
                            if not url or url in seen_urls:
                                continue
                            seen_urls.add(url)
                            findings.append(
                                OsintFinding(
                                    category="account",
                                    value=username,
                                    url=url,
                                    source=str(item.get("name") or item.get("site") or "Sherlock"),
                                    confidence=0.97,
                                    reliability=0.93,
                                    metadata={**item, "registration_confirmed": True, "public_data_only": True},
                                )
                            )
            except Exception as exc:
                parse_error = f"Unable to parse Sherlock CSV: {exc}"

            # Sherlock writes its CSV near the end of a scan. On a bounded
            # timeout, already printed claimed URLs are still valuable.
            for finding in self._stdout_findings(execution.stdout, username):
                url = str(finding.url or "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    findings.append(finding)

        timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
        if findings:
            status = ResultStatus.SUCCESS if execution.success and not parse_error else ResultStatus.PARTIAL
            return OsintResult(
                connector=self.name,
                status=status,
                findings=findings,
                raw_data=parsed_rows if request.save_raw_output else None,
                execution_time=execution.execution_time,
                error=(
                    parse_error
                    or ("Sherlock process budget reached; partial findings retained." if timed_out else None)
                ),
                metadata={
                    "accounts_found": len(findings),
                    "report_format": "csv+stdout-recovery",
                    "local_site_database": True,
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
                error=execution.stderr or execution.stdout or "Sherlock execution failed.",
                metadata={
                    "local_site_database": True,
                    "timed_out": timed_out,
                    "repairable": True,
                    "process_budget_seconds": self._process_budget(request.timeout),
                },
            )

        return OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            findings=[],
            raw_data=parsed_rows if request.save_raw_output else None,
            execution_time=execution.execution_time,
            metadata={
                "accounts_found": 0,
                "report_format": "csv",
                "local_site_database": True,
                "timed_out": False,
            },
        )
