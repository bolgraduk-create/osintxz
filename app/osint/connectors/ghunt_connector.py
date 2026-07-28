"""
GHunt connector.

Integrates GHunt into the
Intelligence Platform.

Responsibilities:

- execute GHunt
- parse JSON output
- convert results to OsintResult

Does NOT:

- store database objects
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


class GHuntConnector(BaseConnector):
    """
    GHunt connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "GHunt"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Searches Google account information "
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
            shutil.which(
                "ghunt",
            )
            is not None
        )

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
                error="GHunt is not installed.",
            )

        execution = self.runner.run(

            [
                "ghunt",
                "email",
                request.target.value,
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

        try:

            data = json.loads(
                execution.stdout,
            )

        except Exception:

            return OsintResult(

                connector=self.name,

                status=ResultStatus.PARTIAL,

                execution_time=execution.execution_time,

                raw_data=execution.stdout,

                error="Unable to parse GHunt output.",

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

        if isinstance(
            data,
            dict,
        ):

            result.add_finding(

                OsintFinding(

                    category="google_account",

                    value=request.target.value,

                    source="GHunt",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=data,

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result