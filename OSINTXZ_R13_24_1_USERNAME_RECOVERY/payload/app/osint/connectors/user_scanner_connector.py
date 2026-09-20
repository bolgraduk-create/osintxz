from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus
from app.osint.runner import ToolRunner


class UserScannerConnector(BaseConnector):
    name = "user_scanner"
    description = "Free public username/account discovery using User Scanner."
    supported_targets = {OsintTargetType.EMAIL, OsintTargetType.USERNAME}

    USERNAME_CATEGORIES = ("social", "dev", "creator", "community", "gaming", "donation")

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
    def _prefix(cls) -> list[str]:
        if cls.module_available():
            return [sys.executable, "-X", "utf8", "-m", "user_scanner"]
        executable = cls.executable()
        return [str(executable)] if executable else ["user-scanner"]

    @classmethod
    def _build_command(
        cls,
        *,
        target_type: OsintTargetType,
        value: str,
        output: Path,
        category: str | None = None,
    ) -> list[str]:
        mode_flag = "-e" if target_type is OsintTargetType.EMAIL else "-u"
        command = [*cls._prefix(), mode_flag, value]
        if category and target_type is OsintTargetType.USERNAME:
            command.extend(["-c", category])
        command.extend(["-f", "json", "-o", str(output)])
        return command

    @staticmethod
    def _total_budget(request_timeout: int) -> int:
        return max(55, min(80, int(request_timeout or 15) * 4))

    @staticmethod
    def _category_budget(remaining: float, remaining_categories: int) -> int:
        if remaining <= 1:
            return 1
        fair = int(max(1.0, remaining / max(1, remaining_categories)))
        return max(8, min(18, fair))

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
        started = perf_counter()
        total_budget = self._total_budget(request.timeout)
        payloads: list[Any] = []
        passes: list[dict[str, Any]] = []

        # Username scanning is split by category. One slow/broken category no
        # longer prevents already completed categories from returning results.
        categories: tuple[str | None, ...]
        if target_type is OsintTargetType.USERNAME:
            categories = self.USERNAME_CATEGORIES
        else:
            categories = (None,)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for index, category in enumerate(categories):
                elapsed = perf_counter() - started
                remaining = total_budget - elapsed
                if remaining <= 1:
                    passes.append({"category": category or "all", "status": "budget_exhausted", "records": 0})
                    break
                pass_budget = self._category_budget(remaining, len(categories) - index)
                output = tmp_path / f"user_scanner_{category or 'all'}_{index}.json"
                command = self._build_command(
                    target_type=target_type,
                    value=value,
                    output=output,
                    category=category,
                )
                execution = self.runner.run(
                    command,
                    timeout=min(pass_budget, max(1, int(remaining))),
                    env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
                )
                payload: Any = None
                parse_error = ""
                if output.exists():
                    try:
                        payload = json.loads(output.read_text(encoding="utf-8"))
                        payloads.append(payload)
                    except Exception as exc:
                        parse_error = f"Unable to parse User Scanner JSON: {exc}"
                timed_out = execution.return_code == -1 or "process timeout" in str(execution.stderr or "").casefold()
                passes.append({
                    "category": category or "all",
                    "status": "timeout" if timed_out else ("success" if execution.success else "failed"),
                    "records": len(self._records(payload)) if payload is not None else 0,
                    "error": parse_error or str(execution.stderr or ""),
                    "seconds": round(float(execution.execution_time or 0.0), 2),
                })

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            execution_time=perf_counter() - started,
            raw_data=payloads if request.save_raw_output else None,
        )

        registered_records = 0
        emitted_accounts: set[tuple[str, str]] = set()
        emitted_urls: set[str] = set()
        emitted_usernames: set[str] = set()

        for payload in payloads:
            for record in self._records(payload):
                if not self._is_registered(record):
                    continue
                site_name = self._first_text(record, "site_name", "site", "name", "platform", "service") or "unknown"
                service_url = self._public_url(self._first_value(record, "url", "site_url", "profile_url"))
                account_key = (site_name.casefold(), (service_url or "").casefold())
                if account_key in emitted_accounts:
                    continue
                emitted_accounts.add(account_key)
                registered_records += 1
                extra = record.get("extra") if isinstance(record.get("extra"), dict) else {}
                result.add_finding(
                    OsintFinding(
                        category="account",
                        value=value,
                        source=site_name,
                        url=service_url,
                        confidence=0.92,
                        reliability=0.88,
                        metadata={
                            "registration_confirmed": True,
                            "service": site_name,
                            "status": self._first_text(record, "status", "state", "result"),
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
                                category="url",
                                value=service_url,
                                source=site_name,
                                url=service_url,
                                confidence=0.90,
                                reliability=0.88,
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
                                category="username",
                                value=username,
                                source=site_name,
                                url=service_url,
                                confidence=0.94,
                                reliability=0.88,
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
                                category="url",
                                value=profile_url,
                                source=site_name,
                                url=profile_url,
                                confidence=0.94,
                                reliability=0.90,
                                metadata={
                                    "explicit_profile_url": True,
                                    "service": site_name,
                                    "registration_confirmed": True,
                                    "public_data_only": True,
                                },
                            )
                        )

        timeouts = sum(1 for item in passes if item.get("status") == "timeout")
        failures = sum(1 for item in passes if item.get("status") == "failed")
        if registered_records:
            result.status = ResultStatus.PARTIAL if (timeouts or failures) else ResultStatus.SUCCESS
            if result.status is ResultStatus.PARTIAL:
                result.error = f"User Scanner returned {registered_records} account(s); {timeouts + failures} category pass(es) were incomplete."
        elif timeouts or failures:
            result.status = ResultStatus.PARTIAL
            result.error = "User Scanner category passes were incomplete and returned no confirmed accounts."
        else:
            result.status = ResultStatus.SUCCESS

        result.metadata = {
            "matched_records": registered_records,
            "registered_records": registered_records if target_type is OsintTargetType.EMAIL else 0,
            "username_accounts_found": registered_records if target_type is OsintTargetType.USERNAME else 0,
            "records_found": result.total_findings,
            "target_type": target_type.value,
            "safe_mode": True,
            "public_data_only": True,
            "staged_categories": target_type is OsintTargetType.USERNAME,
            "category_passes": passes,
            "total_budget_seconds": total_budget,
            "partial_results_retained": result.status is ResultStatus.PARTIAL and registered_records > 0,
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
                any(k in node for k in ("status", "site_name", "platform", "service", "site"))
                and any(k in node for k in ("email", "url", "site_url", "site_name", "platform", "service", "site"))
            ):
                records.append(node)
            for key in ("results", "data", "records", "sites", "items", "modules"):
                child = node.get(key)
                if isinstance(child, (list, dict)):
                    visit(child)
        visit(value)
        return records

    @classmethod
    def _is_registered(cls, record: dict[str, Any]) -> bool:
        status = (cls._first_text(record, "status", "state", "result") or "").strip().casefold()
        available = record.get("available")
        if isinstance(available, bool):
            if available is False:
                return True
            if available is True:
                return False
        return status in {"registered", "found", "exists", "taken", "unavailable", "claimed", "used"}

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
        if not 2 <= len(value) <= 128 or "@" in value:
            return False
        return not value.startswith(("http://", "https://"))
