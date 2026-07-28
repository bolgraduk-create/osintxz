"""
VirusTotal connector.

Analyzes indicators using VirusTotal API.

Responsibilities:

- send requests to VirusTotal API
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

from app.core.config import settings
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


class VirusTotalConnector(BaseConnector):
    """
    VirusTotal connector.
    """

    name = "virustotal"

    description = (
        "Analyze IPs, domains, URLs "
        "and hashes using VirusTotal."
    )

    supported_targets = {
        OsintTargetType.IP,
        OsintTargetType.DOMAIN,
        OsintTargetType.URL,
        OsintTargetType.HASH,
    }

    BASE_URL = (
        "https://www.virustotal.com/api/v3"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether VirusTotal API
        credentials are configured.
        """

        return (
            settings.virustotal_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute VirusTotal lookup.
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
                    "VirusTotal API key "
                    "is not configured."
                ),
            )

        endpoint, target_value = (
            self._build_endpoint(
                request.target.target_type,
                request.target.value,
            )
        )

        if endpoint is None:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported VirusTotal target.",
            )

        headers = {
            "x-apikey": (
                settings
                .virustotal_api_key
                .get_secret_value()
            )
        }

        try:

            response = requests.get(
                f"{self.BASE_URL}/{endpoint}/{target_value}",
                headers=headers,
                timeout=request.timeout,
            )

        except requests.RequestException as exc:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
            )

        if response.status_code == 404:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                error="Indicator not found.",
            )

        if response.status_code != 200:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    f"VirusTotal API error: "
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
                    "VirusTotal response."
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

        attributes = (
            data
            .get("data", {})
            .get("attributes", {})
        )

        result.add_finding(
            OsintFinding(
                category="virustotal",
                value=request.target.value,
                source=self.name,
                confidence=1.0,
                reliability=1.0,
                metadata=attributes,
            )
        )

        result.metadata = {
            "records_found": result.total_findings,
        }

        return result

    def _build_endpoint(
        self,
        target_type: OsintTargetType,
        value: str,
    ) -> tuple[str | None, str]:

        if target_type == OsintTargetType.IP:

            return (
                "ip_addresses",
                value,
            )

        if target_type == OsintTargetType.DOMAIN:

            return (
                "domains",
                value,
            )

        if target_type == OsintTargetType.URL:

            return (
                "urls",
                value,
            )

        if target_type == OsintTargetType.HASH:

            return (
                "files",
                value,
            )

        return (
            None,
            value,
        )