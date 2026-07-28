"""
Hybrid Analysis connector.

Retrieves malware intelligence
from Hybrid Analysis API.

Responsibilities:

- query Hybrid Analysis API
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


class HybridAnalysisConnector(BaseConnector):
    """
    Hybrid Analysis connector.
    """

    name = "hybrid_analysis"

    description = (
        "Retrieve malware intelligence "
        "from Hybrid Analysis."
    )

    supported_targets = {
        OsintTargetType.HASH,
        OsintTargetType.FILE,
        OsintTargetType.URL,
    }

    BASE_URL = (
        "https://www.hybrid-analysis.com/api/v2"
    )

    def is_available(
        self,
    ) -> bool:
        """
        Check whether Hybrid Analysis API
        key is configured.
        """

        return (
            settings.hybrid_analysis_api_key
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:
        """
        Execute Hybrid Analysis lookup.
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
                    "Hybrid Analysis API key "
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
            "api-key": (
                settings
                .hybrid_analysis_api_key
                .get_secret_value()
            ),
            "User-Agent": (
                "Falcon Sandbox"
            ),
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
                    "Hybrid Analysis API error: "
                    f"{response.status_code}"
                ),
            )

        try:

            data: Any = response.json()

        except Exception:

            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                raw_data=response.text,
                error=(
                    "Unable to parse "
                    "Hybrid Analysis response."
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
                category="malware_intelligence",
                value=request.target.value,
                source=self.name,
                confidence=1.0,
                reliability=1.0,
                metadata={
                    "response": data,
                },
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
        Build Hybrid Analysis endpoint.
        """

        if target_type == OsintTargetType.HASH:

            return (
                f"search/hash?"
                f"hash={value}"
            )

        if target_type == OsintTargetType.FILE:

            return (
                f"search/hash?"
                f"hash={value}"
            )

        if target_type == OsintTargetType.URL:

            return (
                f"search/terms?"
                f"query={value}"
            )

        return None