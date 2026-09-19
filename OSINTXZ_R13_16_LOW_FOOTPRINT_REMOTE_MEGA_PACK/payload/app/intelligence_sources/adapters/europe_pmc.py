from __future__ import annotations

import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result


_PMID = re.compile(r"^\d{1,12}$")


class EuropePmcAdapter(RemoteSourceAdapter):
    API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 EuropePMC",
        )

    @property
    def source_code(self) -> str:
        return "europe_pmc"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"publication", "author", "doi", "pmid", "academic_author"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = query.value.strip()
        if query.capability in {"author", "academic_author"}:
            expression = f'AUTH:"{value.replace(chr(34), "")}"'
        elif query.capability == "doi":
            expression = f'DOI:"{value.replace(chr(34), "")}"'
        elif query.capability == "pmid" or _PMID.fullmatch(value):
            expression = f'EXT_ID:{value}'
        else:
            expression = value
        try:
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "query": expression,
                    "format": "json",
                    "resultType": "core",
                    "pageSize": min(query.limit, 100),
                    "page": 1,
                },
                timeout=query.timeout,
                max_bytes=4_000_000,
            )
            result_list = payload.get("resultList", {}) if isinstance(payload, dict) else {}
            rows = result_list.get("result", []) if isinstance(result_list, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                pmid = str(row.get("pmid") or row.get("id") or "").strip()
                doi = str(row.get("doi") or "").strip()
                record_id = pmid or doi or str(row.get("title") or "").strip()
                if not record_id:
                    continue
                identifiers: dict[str, str] = {}
                if pmid:
                    identifiers["PMID"] = pmid
                if doi:
                    identifiers["DOI"] = doi
                source_url = (
                    f"https://europepmc.org/article/MED/{pmid}"
                    if pmid
                    else (f"https://doi.org/{doi}" if doi else None)
                )
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=record_id,
                        record_type="publication",
                        display_name=str(row.get("title") or record_id),
                        source_url=source_url,
                        identifiers=identifiers,
                        attributes={
                            "author_string": row.get("authorString"),
                            "journal_title": row.get("journalTitle"),
                            "pub_year": row.get("pubYear"),
                            "first_publication_date": row.get("firstPublicationDate"),
                            "cited_by_count": row.get("citedByCount"),
                            "is_open_access": row.get("isOpenAccess"),
                            "candidate_only": query.capability in {"author", "academic_author"},
                            "identity_inference_prohibited": query.capability in {"author", "academic_author"},
                            "public_data": True,
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
