from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class InternetArchiveMetadataAdapter(RemoteSourceAdapter):
    API = "https://archive.org/advancedsearch.php"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 InternetArchiveMetadata",
        )

    @property
    def source_code(self) -> str:
        return "internet_archive_metadata"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"archive_search", "internet_archive", "historical_document", "keyword", "name"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if len(value) < 2:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="Archive search requires at least two characters.")
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "q": value,
                    "fl[]": ["identifier", "title", "creator", "date", "description", "collection", "mediatype", "publicdate"],
                    "rows": str(min(query.limit, 50)),
                    "page": "1",
                    "output": "json",
                },
                timeout=query.timeout,
                max_bytes=3_000_000,
            )
            response = payload.get("response") if isinstance(payload, dict) else None
            rows = response.get("docs", []) if isinstance(response, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows[: query.limit]:
                if not isinstance(row, dict):
                    continue
                identifier = str(row.get("identifier") or "").strip()
                title = str(row.get("title") or identifier).strip()
                if not identifier or not title:
                    continue
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=identifier,
                    record_type="internet_archive_item",
                    display_name=title,
                    source_url=f"https://archive.org/details/{identifier}",
                    identifiers={"INTERNET_ARCHIVE_ID": identifier},
                    attributes={
                        "creator": text_list(row.get("creator"), limit=20),
                        "date": row.get("date"),
                        "public_date": row.get("publicdate"),
                        "description": row.get("description"),
                        "collections": text_list(row.get("collection"), limit=30),
                        "media_type": row.get("mediatype"),
                        "candidate_only": query.capability == "name",
                        "metadata_search_only": True,
                        "archive_item_downloaded": False,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "metadata_only": True, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)
