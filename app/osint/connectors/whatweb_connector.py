"""
WhatWeb connector.

Identifies web technologies
using WhatWeb.

Responsibilities:

- execute WhatWeb
- parse JSON output
- convert output to OsintResult

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


class WhatWebConnector(BaseConnector):
    """
    WhatWeb connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "WhatWeb"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Identifies web technologies "
            "using WhatWeb."
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
                "whatweb",
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
                error="WhatWeb is not installed.",
            )

        execution = self.runner.run(

            command=[
                "whatweb",
                "--log-json=-",
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

        except Exception as exc:

            return OsintResult(

                connector=self.name,

                status=ResultStatus.PARTIAL,

                execution_time=execution.execution_time,

                error=str(exc),

                raw_data=execution.stdout,

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

        if isinstance(data, list):

            for host in data:

                plugins = host.get(
                    "plugins",
                    {},
                )

                for technology, info in plugins.items():

                    result.add_finding(

                        OsintFinding(

                            category="technology",

                            value=technology,

                            source="WhatWeb",

                            confidence=1.0,

                            reliability=1.0,

                            metadata=info,

                        )

                    )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result