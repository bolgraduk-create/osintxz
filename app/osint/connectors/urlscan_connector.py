"""Passive urlscan.io historical-search connector.

R13.28.1 deliberately uses the Search API for automatic enrichment. Submitting
new scans is an active operation and must remain an explicit analyst action.
"""

from __future__ import annotations

from typing import Any

import requests

from app.osint.base_connector import BaseConnector
from app.osint.credential_policy import connector_secret
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus


class URLScanConnector(BaseConnector):
    """Search existing urlscan.io scan records without creating new scans."""

    name = "urlscan"

    description = (
        "Search historical urlscan.io scans for domains and URLs."
    )

    supported_targets = {
        OsintTargetType.URL,
        OsintTargetType.DOMAIN,
    }

    BASE_URL = "https://urlscan.io/api/v1"

    def is_available(self) -> bool:
        return bool(connector_secret("urlscan_api_key"))

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        api_key = connector_secret("urlscan_api_key")
        if not api_key:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="URLScan API key is not configured.",
            )

        query = self._build_query(
            request.target.target_type,
            request.target.value,
        )
        if not query:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported URLScan target.",
            )

        requested_limit = int(request.limit or 10)
        size = max(1, min(requested_limit, 25))

        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                headers={"api-key": api_key},
                params={
                    "q": query,
                    "size": size,
                    "datasource": "scans",
                },
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
                error="URLScan HTTP 429 rate limit reached.",
                metadata={"http_status": 429},
            )

        if response.status_code in {401, 403}:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=(
                    "URLScan HTTP "
                    f"{response.status_code} authentication/access failed."
                ),
                metadata={"http_status": response.status_code},
            )

        if response.status_code != 200:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=f"URLScan API error: {response.status_code}",
                metadata={"http_status": response.status_code},
            )

        try:
            data: dict[str, Any] = response.json()
        except Exception:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                raw_data=response.text,
                error="Unable to parse URLScan response.",
            )

        rows = data.get("results")
        if not isinstance(rows, list):
            rows = []

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            raw_data=(
                response.text
                if request.save_raw_output
                else None
            ),
        )

        for row in rows[:size]:
            if not isinstance(row, dict):
                continue

            task = row.get("task") if isinstance(row.get("task"), dict) else {}
            page = row.get("page") if isinstance(row.get("page"), dict) else {}
            stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}

            observed_url = str(
                page.get("url")
                or task.get("url")
                or request.target.value
            ).strip()
            result.add_finding(
                OsintFinding(
                    category="urlscan_search",
                    value=observed_url or request.target.value,
                    url=observed_url or None,
                    source=self.name,
                    confidence=1.0,
                    reliability=1.0,
                    metadata={
                        "query": query,
                        "task": task,
                        "page": page,
                        "stats": stats,
                        "sort": row.get("sort"),
                    },
                )
            )

        result.metadata = {
            "records_found": result.total_findings,
            "reported_total": int(data.get("total") or 0),
            "has_more": bool(data.get("has_more")),
            "query": query,
            "mode": "passive_search",
        }
        return result

    @classmethod
    def _build_query(
        cls,
        target_type: OsintTargetType,
        value: str,
    ) -> str | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None

        if target_type is OsintTargetType.DOMAIN:
            return f'page.domain.keyword:"{cls._escape_query(normalized.casefold())}"'

        if target_type is OsintTargetType.URL:
            return f'task.url.keyword:"{cls._escape_query(normalized)}"'

        return None

    @staticmethod
    def _escape_query(value: str) -> str:
        # Inside a quoted Query String value, protect the two characters that
        # can terminate/change the literal. requests handles URL encoding.
        return str(value or "").replace("\\", "\\\\").replace('"', '\\"')
