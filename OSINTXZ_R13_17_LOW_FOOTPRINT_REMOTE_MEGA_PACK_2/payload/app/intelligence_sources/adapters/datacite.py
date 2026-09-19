from __future__ import annotations

from urllib.parse import quote

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class DataCiteAdapter(RemoteSourceAdapter):
    API = "https://api.datacite.org/dois"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 DataCite",
            extra_headers={"Accept": "application/vnd.api+json"},
        )

    @property
    def source_code(self) -> str:
        return "datacite_public"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"doi", "publication", "dataset", "research_output", "author"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if not value:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="Empty DataCite query.")
        exact = query.capability == "doi"
        try:
            if exact:
                payload = self.client.request_json(
                    "GET",
                    f"{self.API}/{quote(value, safe='/')}",
                    timeout=query.timeout,
                    max_bytes=1_500_000,
                )
                raw_rows = [payload.get("data")] if isinstance(payload, dict) else []
            else:
                payload = self.client.request_json(
                    "GET",
                    self.API,
                    params={"query": value, "page[size]": str(min(query.limit, 25))},
                    timeout=query.timeout,
                    max_bytes=3_000_000,
                )
                raw_rows = payload.get("data", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for item in raw_rows[: query.limit]:
                if not isinstance(item, dict):
                    continue
                attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
                doi = str(attrs.get("doi") or item.get("id") or "").strip()
                titles = attrs.get("titles") if isinstance(attrs.get("titles"), list) else []
                title = next((str(row.get("title") or "").strip() for row in titles if isinstance(row, dict) and row.get("title")), doi)
                if not doi and not title:
                    continue
                creators = []
                for creator in (attrs.get("creators") or [])[:30]:
                    if isinstance(creator, dict):
                        name = str(creator.get("name") or "").strip()
                        if name:
                            creators.append(name)
                subjects = [
                    str(subject.get("subject") or "").strip()
                    for subject in (attrs.get("subjects") or [])[:30]
                    if isinstance(subject, dict) and str(subject.get("subject") or "").strip()
                ]
                rtype = attrs.get("types") if isinstance(attrs.get("types"), dict) else {}
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=doi or str(item.get("id") or title),
                    record_type="doi_metadata",
                    display_name=title or doi,
                    source_url=f"https://doi.org/{doi}" if doi else attrs.get("url"),
                    identifiers={"DOI": doi} if doi else {},
                    attributes={
                        "creators": text_list(creators, limit=30),
                        "publisher": attrs.get("publisher"),
                        "publication_year": attrs.get("publicationYear"),
                        "resource_type": rtype.get("resourceTypeGeneral") or rtype.get("resourceType"),
                        "subjects": text_list(subjects, limit=30),
                        "candidate_only": not exact,
                        "exact_doi_lookup": exact,
                        "public_metadata_only": True,
                        "linked_files_downloaded": False,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "public_api": True, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)
