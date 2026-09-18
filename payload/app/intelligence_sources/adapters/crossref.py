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


class CrossrefAdapter(RemoteSourceAdapter):
    BASE = "https://api.crossref.org/works"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "crossref"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"doi", "work", "publication", "author", "name"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability == "doi":
                doi = query.value.strip()
                payload = self.client.get_json(
                    f"{self.BASE}/{doi}",
                    timeout=query.timeout,
                )
                message = payload.get("message") if isinstance(payload, dict) else None
                items = [message] if isinstance(message, dict) else []
            else:
                payload = self.client.get_json(
                    self.BASE,
                    params={
                        "query.bibliographic": query.value,
                        "rows": min(query.limit, 100),
                    },
                    timeout=query.timeout,
                )
                message = payload.get("message", {}) if isinstance(payload, dict) else {}
                items = message.get("items", []) if isinstance(message, dict) else []
                if not isinstance(items, list):
                    raise ValueError("Malformed Crossref response.")

            records = [
                r for item in items[: query.limit]
                if isinstance(item, dict)
                and (r := self._map(item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records)},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"Crossref HTTP {exc.response.status_code}",
                metadata={"retryable": retryable},
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        doi = str(item.get("DOI") or "").strip()
        titles = item.get("title") or []
        title = str(titles[0]).strip() if isinstance(titles, list) and titles else ""
        if not doi or not title:
            return None
        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = " ".join(
                    filter(None, [
                        str(author.get("given") or "").strip(),
                        str(author.get("family") or "").strip(),
                    ])
                )
                if name:
                    authors.append({
                        "name": name,
                        "orcid": author.get("ORCID"),
                    })
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=doi,
            record_type="publication",
            display_name=title,
            source_url=str(item.get("URL") or f"https://doi.org/{doi}"),
            identifiers={"DOI": doi},
            attributes={
                "type": item.get("type"),
                "publisher": item.get("publisher"),
                "authors": authors,
                "container_title": item.get("container-title"),
                "published": item.get("published"),
                "references_count": item.get("reference-count"),
                "is_referenced_by_count": item.get("is-referenced-by-count"),
                "funder": item.get("funder"),
            },
        )
