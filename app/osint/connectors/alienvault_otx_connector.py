"""
AlienVault OTX connector.

Retrieves threat intelligence
information from AlienVault OTX API.

Responsibilities:

- query AlienVault OTX API
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


class AlienVaultOTXConnector(BaseConnector):
    """
    AlienVault OTX connector.
    """

    name = "alienvault_otx"

    description = (
        "Retrieve threat intelligence "
        "information from AlienVault OTX."
    )

    supported_targets = {
        OsintTargetType.IP,
        OsintTargetType.DOMAIN,
        OsintTargetType.HASH,
        OsintTargetType.URL,
    }

    BASE_URL = (
        "https://otx.alienvault.com/api/v1"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether OTX API key
        is configured.
        """

        return (
            settings.otx_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute AlienVault OTX lookup.
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
                    "AlienVault OTX API key "
                    "is not configured."
                ),
            )

        endpoint = self._build_endpoint(
            request.target.target_type,
            request.target.value,
        )

        if endpoint is None:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        headers = {
            "X-OTX-API-KEY": (
                settings
                .otx_api_key
                .get_secret_value()
            )
        }

        try:

            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
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
                    "AlienVault OTX API error: "
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
                    "AlienVault OTX response."
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
                category="threat_intelligence",
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

    def _build_endpoint(
        self,
        target_type: OsintTargetType,
        value: str,
    ) -> str | None:
        """
        Build OTX API endpoint.
        """

        if target_type == OsintTargetType.IP:

            return (
                f"indicators/IPv4/{value}/general"
            )

        if target_type == OsintTargetType.DOMAIN:

            return (
                f"indicators/domain/{value}/general"
            )

        if target_type == OsintTargetType.HASH:

            return (
                f"indicators/file/{value}/general"
            )

        if target_type == OsintTargetType.URL:

            return (
                f"indicators/url/{value}/general"
            )

        return None