from __future__ import annotations

import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import (
    PublicJsonClient,
    failure_result,
    text_list,
)


_QID = re.compile(r"^Q[1-9]\d*$", re.I)


class WikidataEntitySearchAdapter(RemoteSourceAdapter):
    """Official Wikidata entity search.

    Wikidata explicitly recommends search APIs rather than expensive regex-style
    SPARQL for text/fuzzy discovery. Exact QIDs are fetched directly.
    """

    API = "https://www.wikidata.org/w/api.php"

    def __init__(
        self,
        *,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 WikidataPublicSearch",
    ) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent=user_agent,
        )

    @property
    def source_code(self) -> str:
        return "wikidata_search"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "name",
            "person",
            "organization",
            "location",
            "entity_search",
            "wikidata_id",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability == "wikidata_id" or _QID.fullmatch(query.value):
                return self._by_id(query)
            payload = self.client.request_json(
                "GET",
                self.API,
                params={
                    "action": "wbsearchentities",
                    "search": query.value,
                    "language": "en",
                    "uselang": "en",
                    "format": "json",
                    "limit": min(query.limit, 50),
                },
                timeout=query.timeout,
            )
            rows = payload.get("search", []) if isinstance(payload, dict) else []
            records: list[RemoteSourceRecord] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                qid = str(row.get("id") or "").strip()
                if not _QID.fullmatch(qid):
                    continue
                label = str(row.get("label") or qid).strip()
                match = row.get("match") if isinstance(row.get("match"), dict) else {}
                aliases = text_list(row.get("aliases"), limit=20)
                records.append(
                    RemoteSourceRecord(
                        source=self.source_code,
                        record_id=qid.upper(),
                        record_type="wikidata_entity_candidate",
                        display_name=label,
                        source_url=str(
                            row.get("concepturi")
                            or f"https://www.wikidata.org/wiki/{qid.upper()}"
                        ),
                        identifiers={"WIKIDATA_ID": qid.upper()},
                        attributes={
                            "description": row.get("description"),
                            "aliases": aliases,
                            "match": {
                                "type": match.get("type"),
                                "language": match.get("language"),
                                "text": match.get("text"),
                            },
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
                metadata={
                    "query_mode": "entity_search",
                    "candidate_only": True,
                    "records_found": len(records[: query.limit]),
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _by_id(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        qid = query.value.upper()
        if not _QID.fullmatch(qid):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Malformed Wikidata QID.",
            )
        payload = self.client.request_json(
            "GET",
            self.API,
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "labels|descriptions|aliases",
                "languages": "en",
                "format": "json",
            },
            timeout=query.timeout,
        )
        entity = (
            payload.get("entities", {}).get(qid, {})
            if isinstance(payload, dict)
            else {}
        )
        if not isinstance(entity, dict) or entity.get("missing") is not None:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[],
                metadata={"records_found": 0, "query_mode": "exact_qid"},
            )
        label = (
            (entity.get("labels", {}).get("en") or {}).get("value")
            or qid
        )
        description = (
            (entity.get("descriptions", {}).get("en") or {}).get("value")
        )
        aliases = [
            str(item.get("value") or "").strip()
            for item in (entity.get("aliases", {}).get("en") or [])
            if isinstance(item, dict) and str(item.get("value") or "").strip()
        ][:20]
        record = RemoteSourceRecord(
            source=self.source_code,
            record_id=qid,
            record_type="wikidata_entity",
            display_name=str(label),
            source_url=f"https://www.wikidata.org/wiki/{qid}",
            identifiers={"WIKIDATA_ID": qid},
            attributes={
                "description": description,
                "aliases": aliases,
                "exact_identifier": True,
                "candidate_only": False,
                "public_data": True,
            },
        )
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.SUCCESS,
            records=[record],
            metadata={"records_found": 1, "query_mode": "exact_qid"},
        )
