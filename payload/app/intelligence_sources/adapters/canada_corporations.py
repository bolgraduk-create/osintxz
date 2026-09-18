from __future__ import annotations

import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class CanadaFederalCorporationsAdapter(RemoteSourceAdapter):
    BASE = "https://apigateway-passerelledapi.ised-isde.canada.ca/corporations/api/v1/corporations"

    def __init__(self, *, api_key: str | None = None, client: JsonHttpClient | None = None) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "ca_federal_corporations"

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"corporation_id", "business_number", "company"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"CA"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.api_key:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_CONFIGURED, error="CANADA_CORPORATIONS_API_KEY is not configured.")
        value = re.sub(r"\s+", "", query.value)
        if not re.fullmatch(r"\d+", value):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="Corporation ID/business number must be numeric.")
        try:
            payload = self.client.get_json(f"{self.BASE}/{value}.json", params={"lang": "eng"}, timeout=query.timeout, headers={"user-key": self.api_key})
            item = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else None
            if item is None:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            record = self._map(item)
            if record is None:
                raise ValueError("Malformed Corporations Canada response.")
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[record], metadata={"records_found": 1})
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"Corporations Canada HTTP {exc.response.status_code}", metadata={"retryable": retryable})

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        cid = str(item.get("corporationId") or "").strip()
        name = ""
        for wrapper in item.get("corporationNames") or []:
            entry = wrapper.get("CorporationName") if isinstance(wrapper, dict) else None
            if isinstance(entry, dict) and entry.get("current") is True and entry.get("name"):
                name = str(entry["name"]).strip(); break
        if not name:
            return None
        bn = ""
        if isinstance(item.get("businessNumbers"), dict):
            bn = str(item["businessNumbers"].get("businessNumber") or "").strip()
        return RemoteSourceRecord(source=self.source_code, record_id=cid, record_type="organization", display_name=name, country="CA", source_url=f"https://ised-isde.canada.ca/site/corporations-canada/en/federal-corporation-search?corpId={cid}", identifiers={k:v for k,v in {"CORPORATION_ID":cid,"BUSINESS_NUMBER":bn}.items() if v}, attributes={"identity_confirmed": True, "status": item.get("status"), "act": item.get("act"), "addresses": item.get("adresses") or [], "annual_returns": item.get("annualReturns") or [], "activities": item.get("activities") or []})
