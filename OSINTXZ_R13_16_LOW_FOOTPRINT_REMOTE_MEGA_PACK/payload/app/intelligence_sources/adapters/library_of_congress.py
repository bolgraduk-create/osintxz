from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class LibraryOfCongressAdapter(RemoteSourceAdapter):
    API = "https://www.loc.gov/search/"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 LibraryOfCongress",
        )

    @property
    def source_code(self) -> str:
        return "library_of_congress"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"archive_search", "historical_document", "historical_web"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "q": query.value,
                    "fo": "json",
                    "c": min(query.limit, 50),
                    "sp": 1,
                    "at": "results,pagination",
                },
                timeout=query.timeout,
                max_bytes=4_000_000,
            )
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                source_url = str(row.get("id") or row.get("url") or "").strip()
                record_id = str(row.get("item_id") or source_url or row.get("title") or "").strip()
                if not record_id:
                    continue
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=record_id,
                        record_type="archive_item_candidate",
                        display_name=str(row.get("title") or record_id),
                        source_url=source_url or None,
                        identifiers={"LCCN": str(row.get("lccn")[0])} if isinstance(row.get("lccn"), list) and row.get("lccn") else {},
                        attributes={
                            "date": row.get("date"),
                            "description": text_list(row.get("description"), limit=10),
                            "subject": text_list(row.get("subject"), limit=20),
                            "location": text_list(row.get("location"), limit=20),
                            "contributor": text_list(row.get("contributor"), limit=20),
                            "original_format": text_list(row.get("original_format"), limit=10),
                            "partof": text_list(row.get("partof"), limit=10),
                            "candidate_only": True,
                            "public_archive_metadata": True,
                            "raw_resource_downloaded": False,
                            "no_local_cache": True,
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={"records_found": len(records[: query.limit]), "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)
