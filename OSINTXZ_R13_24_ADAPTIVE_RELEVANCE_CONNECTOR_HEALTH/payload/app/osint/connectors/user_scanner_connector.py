from __future__ import annotations

import importlib.util
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


class UserScannerConnector(BaseConnector):
    name = "user_scanner"
    description = "Free email/username registration discovery using User Scanner."
    supported_targets = {OsintTargetType.EMAIL, OsintTargetType.USERNAME}

    def __init__(self) -> None:
        self.runner = ToolRunner()

    @classmethod
    def module_available(cls) -> bool:
        try:
            return importlib.util.find_spec("user_scanner") is not None
        except Exception:
            return False

    @classmethod
    def executable(cls) -> str | None:
        python_dir = Path(sys.executable).resolve().parent
        for candidate in (python_dir / "user-scanner.exe", python_dir / "user-scanner"):
            if candidate.is_file():
                return str(candidate)
        return shutil.which("user-scanner") or shutil.which("user_scanner")

    def is_available(self) -> bool:
        return self.module_available() or self.executable() is not None

    @classmethod
    def _build_command(
        cls,
        *,
        target_type: OsintTargetType,
        value: str,
        output: Path,
    ) -> list[str]:
        mode_flag = "-e" if target_type is OsintTargetType.EMAIL else "-u"
        # Prefer module execution so the tool is guaranteed to come from the
        # same .venv as OSINTXZ.  Current CLI versions expose -f/-o; the old
        # connector's -t/--no-nsfw flags are intentionally not forced because
        # they are version-specific and can make newer releases exit early.
        if cls.module_available():
            prefix = [sys.executable, "-X", "utf8", "-m", "user_scanner"]
        else:
            executable = cls.executable()
            prefix = [str(executable)] if executable else ["user-scanner"]
        return [*prefix, mode_flag, value, "-f", "json", "-o", str(output)]

    @staticmethod
    def _process_budget(request_timeout: int) -> int:
        return max(30, min(75, int(request_timeout or 15) * 3))

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(connector=self.name, status=ResultStatus.NOT_SUPPORTED, error="Unsupported target.")
        if not self.is_available():
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="User Scanner is not installed in the project Python environment.",
                metadata={
                    "install_hint": r".\.venv\Scripts\python.exe -m pip install --upgrade user-scanner",
                    "public_data_only": True,
                    "repairable": True,
                },
            )

        value = request.target.value.strip()
        target_type = request.target.target_type
        with tempfile.TemporaryDirectory() as tmp:
            suffix = "email" if target_type is OsintTargetType.EMAIL else "username"
            output = Path(tmp) / f"user_scanner_{suffix}.json"
            command = self._build_command(target_type=target_type, value=value, output=output)
            execution = self.runner.run(
                command,
                timeout=self._process_budget(request.timeout),
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
            )
            payload: Any = None
            parse_error = ""
            if output.exists():
                try:
                    payload = json.loads(output.read_text(encoding="utf-8"))
                except Exception as exc:
                    parse_error = f"Unable to parse User Scanner JSON: {exc}"

        timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
        if payload is None:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED if not execution.success else ResultStatus.PARTIAL,
                execution_time=execution.execution_time,
                error=parse_error or execution.stderr or execution.stdout or "User Scanner produced no JSON output file.",
                metadata={
                    "safe_mode": True,
                    "public_data_only": True,
                    "timed_out": timed_out,
                    "repairable": True,
                },
            )

        result = OsintResult(
            connector=self.name,
            status=(ResultStatus.SUCCESS if execution.success and not parse_error else ResultStatus.PARTIAL),
            execution_time=execution.execution_time,
            raw_data=payload if request.save_raw_output else None,
            error=(parse_error or ("User Scanner process budget reached; partial JSON retained." if timed_out else None)),
        )

        registered_records = 0
        emitted_urls: set[str] = set()
        emitted_usernames: set[str] = set()
        for record in self._records(payload):
            if not self._is_registered(record):
                continue
            registered_records += 1
            site_name = self._first_text(record, "site_name", "site", "name", "platform", "service") or "unknown"
            service_url = self._public_url(self._first_value(record, "url", "site_url", "profile_url"))
            extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
            result.add_finding(
                OsintFinding(
                    category="account",
                    value=value,
                    source=self.name,
                    url=service_url,
                    confidence=0.90,
                    reliability=0.88,
                    metadata={
                        "registration_confirmed": True,
                        "service": site_name,
                        "status": self._first_text(record, "status", "state"),
                        "safe_mode": True,
                        "public_data_only": True,
                        "raw_record": record,
                    },
                )
            )
            if service_url:
                key = service_url.casefold().rstrip("/")
                if key not in emitted_urls:
                    emitted_urls.add(key)
                    result.add_finding(
                        OsintFinding(
                            category="url", value=service_url, source=self.name, url=service_url,
                            confidence=0.90, reliability=0.88,
                            metadata={"registration_confirmed": True, "service": site_name, "public_data_only": True},
                        )
                    )
            username = self._first_text(extra, "username", "user_name", "handle")
            if username and self._plausible_username(username):
                key = username.casefold()
                if key not in emitted_usernames:
                    emitted_usernames.add(key)
                    result.add_finding(
                        OsintFinding(
                            category="username", value=username, source=self.name, url=service_url,
                            confidence=0.92, reliability=0.88,
                            metadata={
                                "explicit_source_value": True,
                                "service": site_name,
                                "registration_confirmed": True,
                                "public_data_only": True,
                            },
                        )
                    )
            profile_url = self._public_url(self._first_value(extra, "profile_url", "public_url", "profile"))
            if profile_url:
                key = profile_url.casefold().rstrip("/")
                if key not in emitted_urls:
                    emitted_urls.add(key)
                    result.add_finding(
                        OsintFinding(
                            category="url", value=profile_url, source=self.name, url=profile_url,
                            confidence=0.94, reliability=0.90,
                            metadata={
                                "explicit_profile_url": True,
                                "service": site_name,
                                "registration_confirmed": True,
                                "public_data_only": True,
                            },
                        )
                    )

        result.metadata = {
            "matched_records": registered_records,
            "registered_records": registered_records if target_type is OsintTargetType.EMAIL else 0,
            "username_accounts_found": registered_records if target_type is OsintTargetType.USERNAME else 0,
            "records_found": result.total_findings,
            "target_type": target_type.value,
            "safe_mode": True,
            "public_data_only": True,
            "timed_out": timed_out,
            "partial_results_retained": result.status is ResultStatus.PARTIAL,
            "process_budget_seconds": self._process_budget(request.timeout),
        }
        return result

    @classmethod
    def _records(cls, value: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        def visit(node: Any) -> None:
            if isinstance(node, list):
                for item in node:
                    visit(item)
                return
            if not isinstance(node, dict):
                return
            if (
                any(k in node for k in ("status", "site_name", "platform", "service"))
                and any(k in node for k in ("email", "url", "site_name", "platform", "service"))
            ):
                records.append(node)
            for key in ("results", "data", "records", "sites", "items"):
                child = node.get(key)
                if isinstance(child, (list, dict)):
                    visit(child)
        visit(value)
        return records

    @classmethod
    def _is_registered(cls, record: dict[str, Any]) -> bool:
        status = (cls._first_text(record, "status", "state", "result") or "").strip().casefold()
        return status in {"registered", "found", "exists", "taken", "unavailable", "claimed"}

    @staticmethod
    def _first_value(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value not in {None, ""}:
                return value
        return None

    @classmethod
    def _first_text(cls, mapping: dict[str, Any], *keys: str) -> str | None:
        value = cls._first_value(mapping, *keys)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _public_url(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value if value.startswith(("https://", "http://")) else None

    @staticmethod
    def _plausible_username(value: str) -> bool:
        value = value.strip()
        return 2 <= len(value) <= 128 and "@" not in value and not value.startswith(("http://", "https://"))
