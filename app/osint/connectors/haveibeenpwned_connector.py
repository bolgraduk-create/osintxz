"""
Have I Been Pwned connector.

Checks email breach exposure
using Have I Been Pwned API.

Responsibilities:

- query HIBP API
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


class HaveIBeenPwnedConnector(BaseConnector):
    """
    Have I Been Pwned connector.
    """

    name = "haveibeenpwned"

    description = (
        "Check email breach exposure "
        "using Have I Been Pwned."
    )

    supported_targets = {
        OsintTargetType.EMAIL,
    }

    BASE_URL = (
        "https://haveibeenpwned.com/api/v3"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether HIBP API key
        is configured.
        """

        return (
            settings.haveibeenpwned_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute HIBP lookup.
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
                    "Have I Been Pwned API key "
                    "is not configured."
                ),
            )

        headers = {
            "hibp-api-key": (
                settings
                .haveibeenpwned_api_key
                .get_secret_value()
            ),
            "user-agent": (
                "Intelligence Platform"
            ),
        }

        try:

            response = requests.get(
                (
                    f"{self.BASE_URL}/breachedaccount/"
                    f"{request.target.value}"
                ),
                headers=headers,
                timeout=request.timeout,
                params={
                    "truncateResponse": "false",
                },
            )

        except requests.RequestException as exc:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
            )

        if response.status_code == 404:

            result = OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
            )

            result.metadata = {
                "breaches_found": 0,
            }

            return result

        if response.status_code != 200:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "HIBP API error: "
                    f"{response.status_code}"
                ),
            )

        try:

            data: list[dict[str, Any]] = (
                response.json()
            )

        except Exception:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                raw_data=response.text,
                error=(
                    "Unable to parse "
                    "HIBP response."
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

        for breach in data:

            result.add_finding(
                OsintFinding(
                    category="data_breach",
                    value=request.target.value,
                    source=self.name,
                    confidence=1.0,
                    reliability=1.0,
                    metadata=breach,
                )
            )

        result.metadata = {
            "breaches_found": result.total_findings,
        }

        return result