from __future__ import annotations

import re
import shutil
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

from app.osint.tool_runtime import (
    build_tool_command,
    tool_available,
)


class PhoneInfogaConnector(BaseConnector):
    """
    PhoneInfoga connector.

    PhoneInfoga 2.11.x no longer provides the old
    --output json contract used by earlier versions.

    Production integration parses the stable CLI
    stdout sections produced by:

        phoneinfoga scan -n <number>
    """

    @property
    def name(
        self,
    ) -> str:

        return "PhoneInfoga"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Searches information about "
            "phone numbers using PhoneInfoga."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.PHONE,
        }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return tool_available(
            "phoneinfoga"
        )

    @staticmethod
    def _parse_output(
        stdout: str,
    ) -> dict[str, Any]:

        result: dict[str, Any] = {
            "local": {},
            "search_queries": [],
            "scanner_success_count": None,
        }

        current_scanner: str | None = None
        current_category: str | None = None

        for raw_line in stdout.splitlines():

            line = raw_line.strip()

            if not line:
                continue

            # --------------------------------------------------
            # Scanner section
            # --------------------------------------------------

            if line.startswith(
                "Results for "
            ):

                current_scanner = (
                    line.removeprefix(
                        "Results for "
                    )
                    .strip()
                )

                current_category = None
                continue

            # --------------------------------------------------
            # Google-search categories
            # --------------------------------------------------

            if (
                line.endswith(":")
                and current_scanner
                == "googlesearch"
            ):

                category = (
                    line[:-1]
                    .strip()
                )

                if category:

                    current_category = (
                        category
                    )

                continue

            # --------------------------------------------------
            # URL entries
            # --------------------------------------------------

            if (
                line.startswith("URL:")
                and current_scanner
                == "googlesearch"
            ):

                url = (
                    line.removeprefix(
                        "URL:"
                    )
                    .strip()
                )

                if url:

                    result[
                        "search_queries"
                    ].append(
                        {
                            "scanner": (
                                current_scanner
                            ),
                            "category": (
                                current_category
                            ),
                            "url": url,
                        }
                    )

                continue

            # --------------------------------------------------
            # Local metadata
            # --------------------------------------------------

            if current_scanner == "local":

                local_fields = {
                    "Raw local": "raw_local",
                    "Local": "local",
                    "E164": "e164",
                    "International": (
                        "international"
                    ),
                    "Country": "country",
                }

                for prefix, key in (
                    local_fields.items()
                ):

                    marker = (
                        prefix + ":"
                    )

                    if line.startswith(
                        marker
                    ):

                        value = (
                            line[
                                len(marker):
                            ]
                            .strip()
                        )

                        result[
                            "local"
                        ][key] = value

                        break

            # --------------------------------------------------
            # Scanner summary
            # --------------------------------------------------

            match = re.match(
                r"^(\d+)\s+scanner\(s\)\s+succeeded$",
                line,
                flags=re.IGNORECASE,
            )

            if match:

                result[
                    "scanner_success_count"
                ] = int(
                    match.group(1)
                )

        return result

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
                error="PhoneInfoga is not installed.",
            )

        execution = self.runner.run(
            command=build_tool_command(
                "phoneinfoga",
                "scan",
                "-n",
                request.target.value,
            ),
            timeout=request.timeout,
            env={
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        )

        if not execution.success:

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
                        "PhoneInfoga "
                        "execution failed."
                    )
                ),
            )

        data = self._parse_output(
            execution.stdout
        )

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            execution_time=(
                execution.execution_time
            ),
            raw_data=(
                {
                    "parsed": data,
                    "stdout": (
                        execution.stdout
                    ),
                }
                if request.save_raw_output
                else None
            ),
        )

        # ======================================================
        # Local phone metadata
        # ======================================================

        local = data.get(
            "local",
            {},
        )

        if local:

            result.add_finding(
                OsintFinding(
                    category="phone_metadata",
                    value=(
                        local.get("e164")
                        or request.target.value
                    ),
                    source="PhoneInfoga/local",
                    confidence=1.0,
                    reliability=1.0,
                    metadata=local,
                )
            )

        # ======================================================
        # Search-query findings
        #
        # These are discovery/search leads, not confirmed
        # accounts or confirmed ownership records.
        # ======================================================

        for item in data.get(
            "search_queries",
            [],
        ):

            url = item.get(
                "url"
            )

            category = (
                item.get("category")
                or "General"
            )

            if not url:
                continue

            result.add_finding(
                OsintFinding(
                    category="search_query",
                    value=request.target.value,
                    source=(
                        "PhoneInfoga/"
                        f"{category}"
                    ),
                    url=url,
                    confidence=0.5,
                    reliability=0.5,
                    metadata={
                        "lead_only": True,
                        "scanner": (
                            item.get(
                                "scanner"
                            )
                        ),
                        "category": (
                            category
                        ),
                    },
                )
            )

        result.metadata = {
            "records_found": (
                result.total_findings
            ),
            "phone_metadata_found": (
                bool(local)
            ),
            "search_queries_found": (
                len(
                    data.get(
                        "search_queries",
                        [],
                    )
                )
            ),
            "scanner_success_count": (
                data.get(
                    "scanner_success_count"
                )
            ),
            "output_format": "stdout",
            "phoneinfoga_cli": (
                "2.11-compatible"
            ),
        }

        return result