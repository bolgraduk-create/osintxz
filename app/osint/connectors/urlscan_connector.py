"""
URLScan connector.

Analyzes URLs using URLScan.io API.

Responsibilities:

- submit URLScan API requests
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


class URLScanConnector(BaseConnector):
    """
    URLScan.io connector.
    """

    name = "urlscan"

    description = (
        "Analyze URLs using URLScan.io."
    )

    supported_targets = {
        OsintTargetType.URL,
        OsintTargetType.DOMAIN,
    }

    BASE_URL = (
        "https://urlscan.io/api/v1"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether URLScan API key
        is configured.
        """

        return (
            settings.urlscan_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute URLScan lookup.
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
                    "URLScan API key "
                    "is not configured."
                ),
            )

        headers = {
            "API-Key": (
                settings
                .urlscan_api_key
                .get_secret_value()
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        payload = {
            "url": request.target.value,
            "visibility": "private",
        }

        try:

            response = requests.post(
                f"{self.BASE_URL}/scan/",
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

        if response.status_code not in {
            200,
            201,
        }:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "URLScan API error: "
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
                    "URLScan response."
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
                category="url_analysis",
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