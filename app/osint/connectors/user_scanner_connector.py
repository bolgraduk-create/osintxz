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


class UserScannerConnector(BaseConnector):
    name = "user_scanner"
    description = "Free email registration/account discovery using User Scanner."
    # M021.16.6.3 USERNAME mode
    supported_targets = {
        OsintTargetType.EMAIL,
        OsintTargetType.USERNAME,
    }

    def __init__(self) -> None:
        self.runner = ToolRunner()

    @classmethod
    def executable(cls) -> str | None:
        python_dir = Path(sys.executable).resolve().parent
        for candidate in (
            python_dir / "user-scanner.exe",
            python_dir / "user-scanner",
        ):
            if candidate.is_file():
                return str(candidate)
        return shutil.which("user-scanner") or shutil.which("user_scanner")

    def is_available(self) -> bool:
        return self.executable() is not None

    @classmethod
    def _build_command(
        cls,
        *,
        executable: str,
        target_type: OsintTargetType,
        value: str,
        output: Path,
        timeout: int,
    ) -> list[str]:
        # M021.16.5.2C1.1 force child UTF-8
        mode_flag = (
            "-e"
            if target_type is OsintTargetType.EMAIL
            else "-u"
        )

        return [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "user_scanner",
            mode_flag,
            value,
            "--no-nsfw",
            "-f",
            "json",
            "-o",
            str(output),
            "-t",
            str(max(3, min(int(timeout), 60))),
        ]

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        executable = self.executable()
        if not executable:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="User Scanner is not installed in the project Python environment.",
                metadata={
                    "install_hint": ".\\.venv\\Scripts\\python.exe -m pip install user-scanner",
                    "public_data_only": True,
                },
            )

        value = request.target.value.strip()
        target_type = request.target.target_type

        with tempfile.TemporaryDirectory() as tmp:
            suffix = (
                "email"
                if target_type is OsintTargetType.EMAIL
                else "username"
            )
            output = Path(tmp) / f"user_scanner_{suffix}.json"
            command = self._build_command(
                executable=executable,
                target_type=target_type,
                value=value,
                output=output,
                timeout=request.timeout,
            )

            execution = self.runner.run(
                command,
                timeout=request.timeout,
            )

            if not execution.success:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=execution.stderr or execution.stdout or "User Scanner execution failed.",
                    metadata={
                        "safe_mode": True,
                        "public_data_only": True,
                    },
                )

            if not output.exists():
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    error="User Scanner completed but produced no JSON output file.",
                    metadata={
                        "safe_mode": True,
                        "public_data_only": True,
                    },
                )

            try:
                payload = json.loads(output.read_text(encoding="utf-8"))
            except Exception as exc:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    error=f"Unable to parse User Scanner JSON: {exc}",
                    metadata={
                        "safe_mode": True,
                        "public_data_only": True,
                    },
                )

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            execution_time=execution.execution_time,
            raw_data=payload if request.save_raw_output else None,
        )

        registered_records = 0
        emitted_urls: set[str] = set()
        emitted_usernames: set[str] = set()

        for record in self._records(payload):
            if not self._is_registered(record):
                continue

            registered_records += 1
            site_name = self._first_text(
                record,
                "site_name",
                "site",
                "name",
                "platform",
                "service",
            ) or "unknown"
            service_url = self._public_url(
                self._first_value(
                    record,
                    "url",
                    "site_url",
                    "profile_url",
                )
            )
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
                            category="url",
                            value=service_url,
                            source=self.name,
                            url=service_url,
                            confidence=0.90,
                            reliability=0.88,
                            metadata={
                                "registration_confirmed": True,
                                "service": site_name,
                                "public_data_only": True,
                            },
                        )
                    )

            username = self._first_text(
                extra,
                "username",
                "user_name",
                "handle",
            )
            if username and self._plausible_username(username):
                key = username.casefold()
                if key not in emitted_usernames:
                    emitted_usernames.add(key)
                    result.add_finding(
                        OsintFinding(
                            category="username",
                            value=username,
                            source=self.name,
                            url=service_url,
                            confidence=0.92,
                            reliability=0.88,
                            metadata={
                                "explicit_source_value": True,
                                "service": site_name,
                                "registration_confirmed": True,
                                "public_data_only": True,
                            },
                        )
                    )

            profile_url = self._public_url(
                self._first_value(
                    extra,
                    "profile_url",
                    "public_url",
                    "profile",
                )
            )
            if profile_url:
                key = profile_url.casefold().rstrip("/")
                if key not in emitted_urls:
                    emitted_urls.add(key)
                    result.add_finding(
                        OsintFinding(
                            category="url",
                            value=profile_url,
                            source=self.name,
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

        result.metadata = {
            "matched_records": registered_records,
            "registered_records": (
                registered_records
                if target_type is OsintTargetType.EMAIL
                else 0
            ),
            "username_accounts_found": (
                registered_records
                if target_type is OsintTargetType.USERNAME
                else 0
            ),
            "records_found": result.total_findings,
            "target_type": target_type.value,
            "safe_mode": True,
            "loud_modules_allowed": False,
            "hudson_enabled": False,
            "proxy_mode": False,
            "public_data_only": True,
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
                and any(k in node for k in ("email", "url", "site_name", "platform"))
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
        status = (
            cls._first_text(record, "status", "state", "result") or ""
        ).strip().casefold()

        return status in {
            "registered",
            "found",
            "exists",
            "taken",
            "unavailable",
        }

    @staticmethod
    def _first_value(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = mapping.get(key)
            if value not in {None, ""}:
                return value
        return None

    @classmethod
    def _first_text(
        cls,
        mapping: dict[str, Any],
        *keys: str,
    ) -> str | None:
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
        if not value.startswith(("https://", "http://")):
            return None
        return value

    @staticmethod
    def _plausible_username(value: str) -> bool:
        value = value.strip()
        if not 2 <= len(value) <= 128:
            return False
        if "@" in value:
            return False
        if value.startswith(("http://", "https://")):
            return False
        return True
