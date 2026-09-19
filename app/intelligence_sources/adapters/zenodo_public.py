from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class ZenodoPublicAdapter(RemoteSourceAdapter):
    API = "https://zenodo.org/api/records"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 ZenodoPublic",
        )

    @property
    def source_code(self) -> str:
        return "zenodo_public"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"research_output", "publication", "dataset", "software", "doi", "author"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if not value:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="Empty Zenodo query.")
        qvalue = f'doi:"{value}"' if query.capability == "doi" else value
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={"q": qvalue, "size": str(min(query.limit, 25)), "sort": "bestmatch"},
                timeout=query.timeout,
                max_bytes=3_000_000,
            )
            rows = []
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                hits = payload.get("hits")
                if isinstance(hits, dict) and isinstance(hits.get("hits"), list):
                    rows = hits["hits"]
                elif isinstance(payload.get("results"), list):
                    rows = payload["results"]
            records: list[RemoteSourceRecord] = []
            exact = query.capability == "doi"
            for row in rows[: query.limit]:
                if not isinstance(row, dict):
                    continue
                metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                rid = str(row.get("id") or row.get("conceptrecid") or "").strip()
                doi = str(row.get("doi") or metadata.get("doi") or "").strip()
                title = str(metadata.get("title") or row.get("title") or doi or rid).strip()
                if not title:
                    continue
                creators = []
                for creator in (metadata.get("creators") or [])[:30]:
                    if isinstance(creator, dict):
                        text = str(creator.get("name") or "").strip()
                        if text:
                            creators.append(text)
                links = row.get("links") if isinstance(row.get("links"), dict) else {}
                resource_type = metadata.get("resource_type")
                if isinstance(resource_type, dict):
                    resource_type = resource_type.get("title") or resource_type.get("type")
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=rid or doi or title,
                    record_type="zenodo_record",
                    display_name=title,
                    source_url=str(links.get("html") or links.get("self_html") or "") or (f"https://doi.org/{doi}" if doi else None),
                    identifiers={"DOI": doi} if doi else {},
                    attributes={
                        "creators": text_list(creators, limit=30),
                        "publication_date": metadata.get("publication_date"),
                        "resource_type": resource_type,
                        "description": metadata.get("description"),
                        "keywords": text_list(metadata.get("keywords"), limit=30),
                        "candidate_only": not exact,
                        "exact_doi_lookup": exact,
                        "record_files_downloaded": False,
                        "public_metadata_only": True,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "anonymous_request": True, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)
