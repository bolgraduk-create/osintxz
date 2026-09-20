from __future__ import annotations

import re

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient, failure_result, text_list

_QID = re.compile(r"^Q[1-9]\d*$", re.I)
_DEFAULT_UA = "OSINTXZBot/1.0 (https://github.com/bolgraduk-create/osintxz) WikidataPublicSearch"


class WikidataEntitySearchAdapter(RemoteSourceAdapter):
    """Official Wikidata Action API search with policy-compliant identification."""

    API = "https://www.wikidata.org/w/api.php"

    def __init__(self, *, transport=None, user_agent: str = _DEFAULT_UA) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent=user_agent,
            extra_headers={"Api-User-Agent": user_agent},
        )

    @property
    def source_code(self) -> str:
        return "wikidata_search"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"name", "person", "organization", "location", "entity_search", "wikidata_id"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability == "wikidata_id" or _QID.fullmatch(query.value):
                return self._by_id(query)
            payload = self.client.request_json(
                "GET", self.API,
                params={
                    "action": "wbsearchentities",
                    "search": query.value,
                    "language": "en",
                    "uselang": "en",
                    "format": "json",
                    "formatversion": 2,
                    "limit": min(query.limit, 50),
                    "maxlag": 5,
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
                        source_url=str(row.get("concepturi") or f"https://www.wikidata.org/wiki/{qid.upper()}"),
                        identifiers={"WIKIDATA_ID": qid.upper()},
                        attributes={
                            "description": row.get("description"),
                            "aliases": aliases,
                            "match": {"type": match.get("type"), "language": match.get("language"), "text": match.get("text")},
                            "candidate_only": True,
                            "identity_inference_prohibited": True,
                            "public_data": True,
                            "client_identification": "wikimedia_policy_compliant",
                        },
                    )
                )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records[: query.limit],
                metadata={"query_mode": "entity_search", "candidate_only": True, "records_found": len(records[: query.limit])},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _by_id(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        qid = query.value.upper()
        if not _QID.fullmatch(qid):
            return RemoteAdapterResult(source=self.source_code, status=RemoteAdapterStatus.NOT_SUPPORTED, error="Malformed Wikidata QID.")
        payload = self.client.request_json(
            "GET", self.API,
            params={
                "action": "wbgetentities", "ids": qid,
                "props": "labels|descriptions|aliases", "languages": "en",
                "format": "json", "formatversion": 2, "maxlag": 5,
            },
            timeout=query.timeout,
        )
        entities = payload.get("entities", {}) if isinstance(payload, dict) else {}
        # formatversion=2 may return a list; retain compatibility with v1 dicts.
        entity = {}
        if isinstance(entities, dict):
            entity = entities.get(qid, {})
        elif isinstance(entities, list):
            entity = next((item for item in entities if isinstance(item, dict) and str(item.get("id") or "").upper() == qid), {})
        if not isinstance(entity, dict) or entity.get("missing") is not None:
            return RemoteAdapterResult(source=self.source_code, status=RemoteAdapterStatus.SUCCESS, records=[], metadata={"records_found": 0, "query_mode": "exact_qid"})
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        aliases_raw = entity.get("aliases", {})
        label = ((labels.get("en") or {}).get("value") if isinstance(labels, dict) else None) or qid
        description = ((descriptions.get("en") or {}).get("value") if isinstance(descriptions, dict) else None)
        alias_items = aliases_raw.get("en") if isinstance(aliases_raw, dict) else []
        aliases = [str(item.get("value") or "").strip() for item in (alias_items or []) if isinstance(item, dict) and str(item.get("value") or "").strip()][:20]
        record = RemoteSourceRecord(
            source=self.source_code,
            record_id=qid,
            record_type="wikidata_entity",
            display_name=str(label),
            source_url=f"https://www.wikidata.org/wiki/{qid}",
            identifiers={"WIKIDATA_ID": qid},
            attributes={"description": description, "aliases": aliases, "exact_identifier": True, "candidate_only": False, "public_data": True},
        )
        return RemoteAdapterResult(source=self.source_code, status=RemoteAdapterStatus.SUCCESS, records=[record], metadata={"records_found": 1, "query_mode": "exact_qid"})
