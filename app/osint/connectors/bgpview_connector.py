"""
BGPView connector.

Retrieves ASN and routing information
using the BGPView API.

Responsibilities:

- query BGPView
- parse JSON response
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


class BGPViewConnector(BaseConnector):
    """
    BGPView connector.
    """

    name = "bgpview"

    description = (
        "Retrieve ASN information using BGPView."
    )

    supported_targets = {
        OsintTargetType.IP,
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
            "https://api.bgpview.io/ip/"
            + request.target.value
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

            response = json.loads(
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
                response
                if request.save_raw_output
                else None
            ),

        )

        data = response.get(
            "data",
            {},
        )

        prefixes = data.get(
            "prefixes",
            [],
        )

        for prefix in prefixes:

            result.add_finding(

                OsintFinding(

                    category="prefix",

                    value=prefix.get(
                        "prefix",
                        "",
                    ),

                    source="BGPView",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=prefix,

                )

            )

        if data.get("rir_name"):

            result.add_finding(

                OsintFinding(

                    category="rir",

                    value=data["rir_name"],

                    source="BGPView",

                    confidence=1.0,

                    reliability=1.0,

                    metadata=data,

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result