"""
WhatsMyName connector.

Searches usernames across
supported websites.

Responsibilities:

- execute WhatsMyName
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


class WhatsMyNameConnector(BaseConnector):
    """
    WhatsMyName connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "WhatsMyName"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Searches usernames across "
            "supported websites."
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

        return (
            shutil.which(
                "whatsmyname",
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
                error="WhatsMyName is not installed.",
            )

        execution = self.runner.run(

            [
                "whatsmyname",
                "--json",
                request.target.value,
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

                error="Unable to parse WhatsMyName output.",

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
            list,
        ):

            for item in data:

                result.add_finding(

                    OsintFinding(

                        category="account",

                        value=request.target.value,

                        source=item.get(
                            "site",
                            "WhatsMyName",
                        ),

                        url=item.get(
                            "url",
                        ),

                        confidence=1.0,

                        reliability=1.0,

                        metadata=item,

                    )

                )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result