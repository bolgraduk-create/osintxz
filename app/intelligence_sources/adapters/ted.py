from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


def _first_text(value) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return None
    if isinstance(value, dict):
        for preferred in ("eng", "en"):
            if preferred in value:
                text = _first_text(value[preferred])
                if text:
                    return text
        for item in value.values():
            text = _first_text(item)
            if text:
                return text
    return None


class TedSearchAdapter(RemoteSourceAdapter):
    URL = "https://api.ted.europa.eu/v3/notices/search"
    FIELDS = [
        "publication-number",
        "notice-title",
        "buyer-name",
        "notice-type",
        "publication-date",
    ]

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "eu_ted_search"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"procurement", "notice", "expert_query"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        # value is intentionally the official TED expert-query string. A friendly
        # query builder belongs in Search All, not in this transport adapter.
        body = {
            "query": query.value,
            "fields": self.FIELDS,
            "page": 1,
            "limit": min(query.limit, 250),
            "scope": "ALL",
            "checkQuerySyntax": False,
            "paginationMode": "PAGE_NUMBER",
            "onlyLatestVersions": False,
        }
        try:
            payload = self.client.post_json(
                self.URL,
                json_body=body,
                timeout=query.timeout,
            )
            notices = payload.get("notices", []) if isinstance(payload, dict) else []
            if not isinstance(notices, list):
                raise ValueError("Malformed TED Search API response.")
            records = [
                r for item in notices[: query.limit]
                if isinstance(item, dict) and (r := self._map(item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "total_notice_count": payload.get("totalNoticeCount") if isinstance(payload, dict) else None,
                    "timed_out": payload.get("timedOut") if isinstance(payload, dict) else None,
                    "query_mode": "official_expert_query",
                },
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"TED HTTP {code}",
                metadata={"retryable": retryable, "rate_limited": code == 429},
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        publication = _first_text(item.get("publication-number"))
        if not publication:
            return None
        title = _first_text(item.get("notice-title")) or publication
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=publication,
            record_type="procurement_notice",
            display_name=title,
            source_url=f"https://ted.europa.eu/en/notice/-/detail/{publication}",
            identifiers={"TED_PUBLICATION_NUMBER": publication},
            attributes={
                "notice_type": item.get("notice-type"),
                "publication_date": item.get("publication-date"),
                "buyer_name": item.get("buyer-name"),
                "links": item.get("links"),
            },
        )
