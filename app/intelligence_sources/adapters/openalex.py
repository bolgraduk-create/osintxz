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


class OpenAlexAdapter(RemoteSourceAdapter):
    BASE = "https://api.openalex.org"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: JsonHttpClient | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "openalex"

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"work", "author", "institution", "name"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        endpoint = {
            "work": "works",
            "author": "authors",
            "institution": "institutions",
            "name": "works",
        }.get(query.capability)
        if endpoint is None:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
            )
        if not self.api_key:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_CONFIGURED,
                error="OPENALEX_API_KEY is not configured.",
            )

        try:
            payload = self.client.get_json(
                f"{self.BASE}/{endpoint}",
                params={
                    "search": query.value,
                    "per_page": min(query.limit, 100),
                    "api_key": self.api_key,
                },
                timeout=query.timeout,
            )
            items = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                raise ValueError("Malformed OpenAlex response.")
            records = [
                r for item in items[: query.limit]
                if isinstance(item, dict)
                and (r := self._map(endpoint, item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records)},
            )
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"OpenAlex HTTP {exc.response.status_code}",
                metadata={"retryable": retryable},
            )

    def _map(self, endpoint: str, item: dict) -> RemoteSourceRecord | None:
        rid = str(item.get("id") or "").strip()
        name = str(
            item.get("display_name")
            or item.get("title")
            or ""
        ).strip()
        if not rid or not name:
            return None
        record_type = {
            "works": "publication",
            "authors": "researcher",
            "institutions": "research_organization",
        }[endpoint]
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=rid,
            record_type=record_type,
            display_name=name,
            source_url=rid if rid.startswith("http") else None,
            identifiers={"OPENALEX": rid},
            attributes={
                "cited_by_count": item.get("cited_by_count"),
                "works_count": item.get("works_count"),
                "orcid": item.get("orcid"),
                "doi": item.get("doi"),
                "publication_year": item.get("publication_year"),
                "country_code": item.get("country_code"),
                "type": item.get("type"),
                "ids": item.get("ids"),
            },
        )
