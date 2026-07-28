"""
crt.sh connector.

Searches Certificate Transparency logs
using crt.sh.

Responsibilities:

- query crt.sh
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


class CrtShConnector(BaseConnector):
    """
    crt.sh connector.
    """

    name = "crtsh"

    description = (
        "Search Certificate Transparency logs using crt.sh."
    )

    supported_targets = {
        OsintTargetType.DOMAIN,
    }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return shutil.which(
            "curl",
        ) is not None

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

        url = (
            "https://crt.sh/?q=%25."
            + request.target.value
            + "&output=json"
        )

        execution = self.runner.run(

            [
                "curl",
                "-L",
                url,
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
                execution.stdout
                if request.save_raw_output
                else None
            ),

        )

        seen = set()

        for item in data:

            value = item.get(
                "name_value",
                "",
            )

            for domain in value.split("\n"):

                domain = domain.strip()

                if (
                    not domain
                    or domain in seen
                ):
                    continue

                seen.add(domain)

                result.add_finding(

                    OsintFinding(

                        category="certificate",

                        value=domain,

                        source="crt.sh",

                        confidence=1.0,

                        reliability=1.0,

                        metadata=item,

                    )

                )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result