from __future__ import annotations

import json
import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class AustraliaAbnLookupAdapter(RemoteSourceAdapter):
    BASE = "https://abr.business.gov.au/json"
    MAX_BYTES = 2_000_000

    def __init__(self, *, guid: str | None = None, transport=None) -> None:
        self.guid = (guid or "").strip() or None
        self.transport = transport

    @property
    def source_code(self) -> str:
        return "au_abn_lookup"

    @property
    def configured(self) -> bool:
        return self.guid is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"abn", "acn", "company_name", "organization", "name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"AU"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.guid:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_CONFIGURED, error="ABN_LOOKUP_GUID is not configured.")
        value = re.sub(r"\s+", "", query.value) if query.capability in {"abn", "acn"} else query.value.strip()
        if query.capability == "abn" and not re.fullmatch(r"\d{11}", value):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="ABN must contain 11 digits.")
        if query.capability == "acn" and not re.fullmatch(r"\d{9}", value):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="ACN must contain 9 digits.")
        endpoint, params = self._request(query.capability, value, query.limit)
        try:
            payload = self._get_jsonp(endpoint, params=params, timeout=query.timeout)
            records = self._map_payload(query.capability, payload, query.limit)
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found": len(records), "credential_used": True})
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"ABN Lookup HTTP {exc.response.status_code}", metadata={"retryable": retryable})

    def _request(self, capability: str, value: str, limit: int):
        common = {"callback": "callback", "guid": self.guid}
        if capability == "abn":
            return "AbnDetails.aspx", {**common, "abn": value}
        if capability == "acn":
            return "AcnDetails.aspx", {**common, "acn": value}
        return "MatchingNames.aspx", {**common, "name": value, "maxResults": min(limit, 100)}

    def _get_jsonp(self, endpoint: str, *, params: dict, timeout: int):
        with httpx.Client(timeout=httpx.Timeout(float(timeout)), transport=self.transport, follow_redirects=False, headers={"User-Agent": "OSINTXZ/1.0 ABNLookup", "Accept": "application/javascript"}) as client:
            response = client.get(f"{self.BASE}/{endpoint}", params=params)
            response.raise_for_status()
            raw = response.content
            if len(raw) > self.MAX_BYTES:
                raise ValueError("ABN Lookup response exceeds limit.")
        text = raw.decode("utf-8-sig").strip()
        match = re.fullmatch(r"callback\((.*)\)\s*;?", text, re.DOTALL)
        if not match:
            raise ValueError("Malformed ABN Lookup JSONP response.")
        return json.loads(match.group(1))

    def _map_payload(self, capability: str, payload, limit: int) -> list[RemoteSourceRecord]:
        if capability in {"abn", "acn"}:
            return [r] if (r := self._map_detail(payload, exact=True)) else []
        names = payload.get("Names", []) if isinstance(payload, dict) else []
        out = []
        for item in names[:limit] if isinstance(names, list) else []:
            if not isinstance(item, dict):
                continue
            abn = str(item.get("Abn") or "").replace(" ", "")
            name = str(item.get("Name") or "").strip()
            if abn and name:
                out.append(RemoteSourceRecord(source=self.source_code, record_id=abn, record_type="organization", display_name=name, country="AU", source_url=f"https://abr.business.gov.au/ABN/View?abn={abn}", identifiers={"ABN": abn}, attributes={"candidate_only": True, "identity_confirmed": False, "score": item.get("Score"), "state": item.get("State"), "postcode": item.get("Postcode")}))
        return out

    def _map_detail(self, item, *, exact: bool) -> RemoteSourceRecord | None:
        if not isinstance(item, dict):
            return None
        abn = str(item.get("Abn") or "").replace(" ", "")
        name = str(item.get("EntityName") or "").strip()
        if not abn or not name:
            return None
        acn = str(item.get("Acn") or "").replace(" ", "")
        return RemoteSourceRecord(source=self.source_code, record_id=abn, record_type="organization", display_name=name, country="AU", source_url=f"https://abr.business.gov.au/ABN/View?abn={abn}", identifiers={k:v for k,v in {"ABN":abn,"ACN":acn}.items() if v}, attributes={"candidate_only": not exact, "identity_confirmed": exact, "abn_status": item.get("AbnStatus"), "entity_type": item.get("EntityTypeName"), "gst": item.get("Gst"), "address_state": item.get("AddressState"), "address_postcode": item.get("AddressPostcode"), "business_names": item.get("BusinessName") or []})
