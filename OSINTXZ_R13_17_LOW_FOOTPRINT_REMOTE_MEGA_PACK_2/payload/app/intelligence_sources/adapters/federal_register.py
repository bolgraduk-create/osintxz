from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class FederalRegisterAdapter(RemoteSourceAdapter):
    API = "https://www.federalregister.gov/api/v1/documents.json"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 FederalRegister",
        )

    @property
    def source_code(self) -> str:
        return "us_federal_register"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"federal_register", "regulatory_document", "regulation_search", "name", "organization", "keyword"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if len(value) < 2:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Federal Register search requires at least two characters.",
            )
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "conditions[term]": value,
                    "per_page": str(min(query.limit, 50)),
                    "order": "relevance",
                },
                timeout=query.timeout,
                max_bytes=3_000_000,
            )
            rows = payload.get("results", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows[: query.limit]:
                if not isinstance(row, dict):
                    continue
                number = str(row.get("document_number") or "").strip()
                title = str(row.get("title") or number).strip()
                if not title:
                    continue
                agencies = []
                for agency in row.get("agencies") or []:
                    if isinstance(agency, dict):
                        text = str(agency.get("name") or "").strip()
                    else:
                        text = str(agency or "").strip()
                    if text:
                        agencies.append(text)
                rid = number or str(row.get("html_url") or title)
                records.append(RemoteSourceRecord(
                    source=self.source_code,
                    record_id=rid,
                    record_type="federal_register_document",
                    display_name=title,
                    source_url=str(row.get("html_url") or "") or None,
                    country="US",
                    identifiers={"FEDERAL_REGISTER_DOCUMENT": number} if number else {},
                    attributes={
                        "document_type": row.get("type"),
                        "abstract": row.get("abstract"),
                        "publication_date": row.get("publication_date"),
                        "effective_on": row.get("effective_on"),
                        "agencies": text_list(agencies, limit=20),
                        "citation": row.get("citation"),
                        "mention_only": True,
                        "candidate_only": query.capability in {"name", "organization"},
                        "mention_is_not_identity_confirmation": True,
                        "linked_pdf_downloaded": False,
                        "raw_response_stored": False,
                        "no_local_cache": True,
                    },
                ))
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)
