"""
Aquatone connector.

Creates screenshots of web services.

Responsibilities:

- execute Aquatone
- parse output
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

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


class AquatoneConnector(BaseConnector):
    """
    Aquatone connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Aquatone"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Capture screenshots of "
            "web services."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.DOMAIN,
            OsintTargetType.URL,
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
                "aquatone",
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
                error="Aquatone is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            output = Path(temp)

            execution = self.runner.run(

                command=[
                    "aquatone",
                    "-out",
                    str(output),
                ],

                stdin=request.target.value,

                timeout=request.timeout,

            )

            if not execution.success:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.FAILED,

                    execution_time=execution.execution_time,

                    error=execution.stderr,

                )

            findings: list[
                OsintFinding
            ] = []

            screenshots = output / "screenshots"

            if screenshots.exists():

                for image in screenshots.glob("*"):

                    findings.append(

                        OsintFinding(

                            category="screenshot",

                            value=image.name,

                            source="Aquatone",

                            confidence=1.0,

                            reliability=1.0,

                            metadata={

                                "path": str(image),

                            },

                        )

                    )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            findings=findings,

        )

        result.metadata = {

            "screenshots": result.total_findings,

        }

        return result