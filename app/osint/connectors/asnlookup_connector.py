"""
ASN Lookup connector.

Retrieves ASN information
for domains and IP addresses.

Responsibilities:

- query HackerTarget ASN API
- parse response
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


class ASNLookupConnector(BaseConnector):
    """
    ASN Lookup connector.
    """

    name = "asnlookup"

    description = (
        "Retrieve ASN information for IPs and domains."
    )

    supported_targets = {
        OsintTargetType.IP,
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
            "https://api.hackertarget.com/aslookup/?q="
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

        for line in execution.stdout.splitlines():

            line = line.strip()

            if not line:
                continue

            result.add_finding(

                OsintFinding(

                    category="asn",

                    value=line,

                    source="ASN Lookup",

                    confidence=1.0,

                    reliability=1.0,

                    metadata={},

                )

            )

        result.metadata = {

            "records_found": result.total_findings,

        }

        return result