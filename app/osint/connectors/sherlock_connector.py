"""
Sherlock connector.

Integrates Sherlock username search
into the Intelligence Platform.

Responsibilities:

- execute Sherlock
- parse JSON results
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
- perform workflow logic
"""

from __future__ import annotations

import json
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
    """

    @property
    def name(
        self,
    ) -> str:

        return "Sherlock"

    @property
    def description(
        self,
    ) -> str:

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

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:
        """
        Check whether Sherlock
        is installed.
        """

        return (
            shutil.which("sherlock")
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute Sherlock.
        """

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

            output = Path(temp)

            command = [

                "sherlock",

                request.target.value,

                "--json",

                str(output),

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

                    error=execution.stderr,

                )

            json_file = (
                output /
                f"{request.target.value}.json"
            )

            if not json_file.exists():

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.FAILED,

                    execution_time=execution.execution_time,

                    error="Sherlock JSON not produced.",

                )

            try:

                data = json.loads(
                    json_file.read_text(
                        encoding="utf-8",
                    )
                )

            except Exception as exc:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.FAILED,

                    execution_time=execution.execution_time,

                    error=str(exc),

                )

            findings: list[
                OsintFinding
            ] = []

            for website, info in data.items():

                if not isinstance(
                    info,
                    dict,
                ):
                    continue

                url = info.get(
                    "url_user",
                )

                if not url:
                    continue

                findings.append(

                    OsintFinding(

                        category="account",

                        value=request.target.value,

                        url=url,

                        source=website,

                        confidence=1.0,

                        reliability=1.0,

                        metadata=info,

                    )

                )

            return OsintResult(

                connector=self.name,

                status=ResultStatus.SUCCESS,

                findings=findings,

                raw_data=(
                    data
                    if request.save_raw_output
                    else None
                ),

                execution_time=execution.execution_time,

                metadata={

                    "accounts_found": len(findings),

                },

            )