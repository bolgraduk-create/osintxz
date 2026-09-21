"""
AbuseIPDB connector.

Checks IP reputation using AbuseIPDB API.

Responsibilities:

- query AbuseIPDB API
- parse JSON response
- convert results to OsintResult

Does NOT:

- store database objects
- call AI
- perform workflow logic
"""

from __future__ import annotations

from typing import Any

import requests

from app.osint.base_connector import BaseConnector
from app.osint.credential_policy import connector_secret
from app.osint.models import (
    ConnectorRequest,
    OsintTargetType,
)
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)


class AbuseIPDBConnector(BaseConnector):
    """
    AbuseIPDB connector.
    """

    name = "abuseipdb"

    description = (
        "Check IP reputation using "
        "AbuseIPDB."
    )

    supported_targets = {
        OsintTargetType.IP,
    }

    BASE_URL = (
        "https://api.abuseipdb.com/api/v2"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether AbuseIPDB API key
        is configured.
        """

        return bool(connector_secret("abuseipdb_api_key"))

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute AbuseIPDB lookup.
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
                error=(
                    "AbuseIPDB API key "
                    "is not configured."
                ),
            )

        headers = {
            "Key": connector_secret("abuseipdb_api_key"),
            "Accept": "application/json",
        }

        params = {
            "ipAddress": (
                request.target.value
            ),
            "maxAgeInDays": 90,
        }

        try:

            response = requests.get(
                f"{self.BASE_URL}/check",
                headers=headers,
                params=params,
                timeout=request.timeout,
            )

        except requests.RequestException as exc:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
            )

        if response.status_code == 429:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error="AbuseIPDB HTTP 429 rate limit reached.",
                metadata={"http_status": 429},
            )

        if response.status_code in {401, 403}:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "AbuseIPDB HTTP "
                    f"{response.status_code} authentication/access failed."
                ),
                metadata={"http_status": response.status_code},
            )

        if response.status_code == 404:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                error="IP information not found.",
            )

        if response.status_code != 200:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "AbuseIPDB API error: "
                    f"{response.status_code}"
                ),
            )

        try:

            data: dict[str, Any] = (
                response.json()
            )

        except Exception:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                raw_data=response.text,
                error=(
                    "Unable to parse "
                    "AbuseIPDB response."
                ),
            )

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            raw_data=(
                response.text
                if request.save_raw_output
                else None
            ),
        )

        result.add_finding(
            OsintFinding(
                category="ip_reputation",
                value=request.target.value,
                source=self.name,
                confidence=1.0,
                reliability=1.0,
                metadata=data,
            )
        )

        result.metadata = {
            "records_found": result.total_findings,
        }

        return result