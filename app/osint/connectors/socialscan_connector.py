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


class SocialScanConnector(BaseConnector):
    """
    SocialScan connector.

    SocialScan 2.x uses:

        socialscan <query> --json <output-file>
    """

    @property
    def name(self) -> str:
        return "SocialScan"

    @property
    def description(self) -> str:
        return (
            "Searches usernames and email "
            "addresses across supported services."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.USERNAME,
            OsintTargetType.EMAIL,
        }

    def __init__(self) -> None:
        self.runner = ToolRunner()

    def is_available(self) -> bool:
        return (
            shutil.which(
                "socialscan"
            )
            is not None
        )

    @staticmethod
    def _iter_records(
        data: Any,
    ):

        if isinstance(data, list):

            for item in data:

                if isinstance(
                    item,
                    dict,
                ):
                    yield item

            return

        if not isinstance(
            data,
            dict,
        ):
            return

        # Common layouts:
        # {query: [records]}
        # {"results": [...]}
        # {"results": {query: [...]}}
        for key in (
            "results",
            "data",
        ):

            value = data.get(key)

            if isinstance(value, list):

                for item in value:

                    if isinstance(
                        item,
                        dict,
                    ):
                        yield item

                return

            if isinstance(value, dict):

                for child in (
                    value.values()
                ):

                    if isinstance(
                        child,
                        list,
                    ):

                        for item in child:

                            if isinstance(
                                item,
                                dict,
                            ):
                                yield item

                return

        for value in data.values():

            if isinstance(value, list):

                for item in value:

                    if isinstance(
                        item,
                        dict,
                    ):
                        yield item

            elif isinstance(
                value,
                dict,
            ):
                yield value

    @staticmethod
    def _as_bool(
        value: Any,
    ) -> bool | None:

        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return bool(value)

        if isinstance(value, str):

            lowered = (
                value
                .strip()
                .lower()
            )

            if lowered in {
                "true",
                "yes",
                "1",
            }:
                return True

            if lowered in {
                "false",
                "no",
                "0",
            }:
                return False

        return None


    @classmethod
    def _is_used(
        cls,
        item: dict[str, Any],
    ) -> bool:

        available = cls._as_bool(
            item.get("available")
        )

        valid = cls._as_bool(
            item.get("valid")
        )

        success = cls._as_bool(
            item.get("success")
        )

        # Most reliable SocialScan result:
        # query completed successfully,
        # input is valid,
        # identifier is NOT available.
        if (
            success is True
            and valid is True
            and available is False
        ):
            return True

        # Explicit availability result.
        if available is True:
            return False

        for key in (
            "exists",
            "claimed",
            "used",
            "registered",
        ):

            value = cls._as_bool(
                item.get(key)
            )

            if value is True:
                return True

        status = item.get(
            "status"
        )

        if isinstance(status, str):

            lowered = (
                status
                .strip()
                .lower()
            )

            if lowered in {
                "available",
                "free",
                "not found",
                "not_found",
            }:
                return False

            if lowered in {
                "used",
                "claimed",
                "registered",
                "exists",
                "taken",
                "found",
                "unavailable",
            }:
                return True

        return False

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
                error="SocialScan is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = (
                Path(temp)
                / "result.json"
            )

            command = [
                "socialscan",
                request.target.value,
                "--json",
                str(output),
                "--show-urls",
            ]

            execution = self.runner.run(
                command=command,
                timeout=request.timeout,
            )

            if not execution.success:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        execution.stderr
                        or execution.stdout
                        or "SocialScan execution failed."
                    ),
                )

            if not output.exists():
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.PARTIAL,
                    execution_time=execution.execution_time,
                    raw_data=(
                        execution.stdout
                        if request.save_raw_output
                        else None
                    ),
                    error="SocialScan JSON report was not produced.",
                )

            try:

                data = json.loads(
                    output.read_text(
                        encoding="utf-8",
                    )
                )

            except Exception as exc:
                return OsintResult(
                    connector=self.name,
                    status=ResultStatus.FAILED,
                    execution_time=execution.execution_time,
                    error=(
                        "Unable to parse SocialScan JSON: "
                        f"{exc}"
                    ),
                )

            result = OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                execution_time=execution.execution_time,
                raw_data=(
                    data
                    if request.save_raw_output
                    else None
                ),
            )

            for item in self._iter_records(
                data
            ):

                if not self._is_used(
                    item
                ):
                    continue

                source = (
                    item.get("platform")
                    or item.get("service")
                    or item.get("name")
                    or "SocialScan"
                )

                url = (
                    item.get("url")
                    or item.get("link")
                    or item.get("profile_url")
                )

                result.add_finding(
                    OsintFinding(
                        category="account",
                        value=request.target.value,
                        source=str(
                            source
                        ),
                        url=url,
                        confidence=1.0,
                        reliability=1.0,
                        metadata=item,
                    )
                )

            result.metadata = {
                "records_found": (
                    result.total_findings
                ),
                "report_format": "json",
            }

            return result
