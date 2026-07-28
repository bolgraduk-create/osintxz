"""
Holehe connector.

Searches account registrations
using an email address.

Responsibilities:

- execute Holehe
- parse results
- produce OsintResult

Does NOT:

- store data
- create entities
- call AI
"""

from __future__ import annotations

import json
import shutil

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


class HoleheConnector(BaseConnector):
    """
    Holehe connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Holehe"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Searches account registrations "
            "using an email address."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.EMAIL,
        }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return (
            shutil.which("holehe")
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute Holehe.
        """

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
                error="Holehe is not installed.",
            )

        execution = self.runner.run(
            [
                "holehe",
                request.target.value,
                "--only-used",
                "--json",
            ],
            timeout=request.timeout,
        )

        if not execution.success:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                execution_time=execution.execution_time,
                error=execution.stderr,
            )

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            execution_time=execution.execution_time,
            raw_data=(
                execution.stdout
                if request.save_raw_output
                else None
            ),
        )

        try:

            data = json.loads(
                execution.stdout,
            )

        except Exception:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                execution_time=execution.execution_time,
                error="Unable to parse Holehe output.",
                raw_data=execution.stdout,
            )

        if isinstance(
            data,
            dict,
        ):
            data = [data]

        for item in data:

            result.add_finding(

                OsintFinding(

                    category="account",

                    value=request.target.value,

                    source="Holehe",

                    url=item.get(
                        "domain",
                    ),

                    confidence=1.0,

                    reliability=1.0,

                    metadata=item,

                )

            )

        result.metadata = {

            "accounts_found": result.total_findings,

        }

        return result