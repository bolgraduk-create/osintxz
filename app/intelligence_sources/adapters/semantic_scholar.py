from __future__ import annotations

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list


class SemanticScholarAdapter(RemoteSourceAdapter):
    BASE = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 SemanticScholar",
        )

    @property
    def source_code(self) -> str:
        return "semantic_scholar"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"academic_author", "author", "paper", "publication"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability in {"academic_author", "author"}:
                return self._authors(query)
            return self._papers(query)
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _authors(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        payload = self.client.request_json(
            "GET",
            f"{self.BASE}/author/search",
            params={
                "query": query.value,
                "limit": min(query.limit, 100),
                "fields": "authorId,name,url,paperCount,citationCount,hIndex,affiliations,externalIds",
            },
            timeout=query.timeout,
            max_bytes=2_000_000,
        )
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        records: list[RemoteSourceRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            author_id = str(row.get("authorId") or "").strip()
            if not author_id:
                continue
            identifiers = {"SEMANTIC_SCHOLAR_AUTHOR_ID": author_id}
            external = row.get("externalIds") if isinstance(row.get("externalIds"), dict) else {}
            if external.get("ORCID"):
                identifiers["ORCID"] = str(external["ORCID"])
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=f"author:{author_id}",
                    record_type="academic_author_candidate",
                    display_name=str(row.get("name") or author_id),
                    source_url=str(row.get("url") or f"https://www.semanticscholar.org/author/{author_id}"),
                    identifiers=identifiers,
                    attributes={
                        "paper_count": row.get("paperCount"),
                        "citation_count": row.get("citationCount"),
                        "h_index": row.get("hIndex"),
                        "affiliations": text_list(row.get("affiliations"), limit=20),
                        "candidate_only": True,
                        "identity_inference_prohibited": True,
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

    def _papers(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        payload = self.client.request_json(
            "GET",
            f"{self.BASE}/paper/search",
            params={
                "query": query.value,
                "limit": min(query.limit, 100),
                "fields": "paperId,title,url,year,authors,venue,citationCount,externalIds,publicationDate",
            },
            timeout=query.timeout,
            max_bytes=3_000_000,
        )
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        records: list[RemoteSourceRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            paper_id = str(row.get("paperId") or "").strip()
            if not paper_id:
                continue
            ext = row.get("externalIds") if isinstance(row.get("externalIds"), dict) else {}
            identifiers = {"SEMANTIC_SCHOLAR_PAPER_ID": paper_id}
            for key in ("DOI", "PubMed", "ArXiv"):
                if ext.get(key):
                    identifiers[key.upper()] = str(ext[key])
            authors = []
            for author in row.get("authors") or []:
                if isinstance(author, dict) and author.get("name"):
                    authors.append(str(author["name"]))
                if len(authors) >= 20:
                    break
            records.append(
                RemoteSourceRecord(
                    source=self.source_code,
                    record_id=f"paper:{paper_id}",
                    record_type="publication",
                    display_name=str(row.get("title") or paper_id),
                    source_url=str(row.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"),
                    identifiers=identifiers,
                    attributes={
                        "year": row.get("year"),
                        "publication_date": row.get("publicationDate"),
                        "venue": row.get("venue"),
                        "citation_count": row.get("citationCount"),
                        "authors": authors,
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
