"""
PhoneInfoga connector.

Searches information about
phone numbers using PhoneInfoga.

Responsibilities:

- execute PhoneInfoga
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


class PhoneInfogaConnector(BaseConnector):
    """
    PhoneInfoga connector.
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
        """
        Check whether PhoneInfoga
        is installed.
        """

        return (
            shutil.which(
                "phoneinfoga",
            )
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute PhoneInfoga.
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
                error="PhoneInfoga is not installed.",
            )

        execution = self.runner.run(

            [
                "phoneinfoga",
                "scan",
                "-n",
                request.target.value,
                "--output",
                "json",
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

                error="Unable to parse PhoneInfoga output.",

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

                    category="phone",

                    value=request.target.value,

                    source="PhoneInfoga",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=data,

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result