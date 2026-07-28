"""
Intelligence X connector.

Searches intelligence data
using Intelligence X API.

Responsibilities:

- query Intelligence X API
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


class IntelligenceXConnector(BaseConnector):
    """
    Intelligence X connector.
    """

    name = "intelligence_x"

    description = (
        "Search intelligence data "
        "using Intelligence X API."
    )

    supported_targets = {
        OsintTargetType.EMAIL,
        OsintTargetType.DOMAIN,
        OsintTargetType.URL,
        OsintTargetType.IP,
        OsintTargetType.HASH,
        OsintTargetType.USERNAME,
    }

    BASE_URL = (
        "https://2.intelx.io"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether Intelligence X API
        key is configured.
        """

        return (
            settings.intelligencex_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute Intelligence X search.
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
                    "Intelligence X API key "
                    "is not configured."
                ),
            )

        headers = {
            "x-key": (
                settings
                .intelligencex_api_key
                .get_secret_value()
            ),
        }

        payload = {
            "term": request.target.value,
            "maxresults": 10,
            "media": 0,
            "sort": 4,
            "terminate": [],
        }

        try:

            response = requests.post(
                (
                    f"{self.BASE_URL}"
                    "/intelligent/search"
                ),
                headers=headers,
                json=payload,
                timeout=request.timeout,
            )

        except requests.RequestException as exc:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
            )

        if response.status_code != 200:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "Intelligence X API error: "
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
                    "Intelligence X response."
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
                category="intelligence_search",
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