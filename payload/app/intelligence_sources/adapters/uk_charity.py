from __future__ import annotations

import re
from urllib.parse import quote
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class UkCharityCommissionAdapter(RemoteSourceAdapter):
    BASE = "https://api.charitycommission.gov.uk/register/api"

    def __init__(self, *, api_key: str | None = None, client: JsonHttpClient | None = None) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "uk_charity_commission"

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"charity_name", "charity_number", "organization", "name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"GB"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.api_key:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_CONFIGURED, error="CHARITY_COMMISSION_API_KEY is not configured.")
        exact = query.capability == "charity_number"
        if exact:
            number = re.sub(r"\s+", "", query.value)
            if not re.fullmatch(r"\d+", number):
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="Charity number must be numeric.")
            url = f"{self.BASE}/charityRegNumber/{number}/0"
        else:
            url = f"{self.BASE}/searchCharityName/{quote(query.value, safe='')}"
        try:
            payload = self.client.get_json(url, timeout=query.timeout, headers={"Ocp-Apim-Subscription-Key": self.api_key})
            items = payload if isinstance(payload, list) else ([payload] if isinstance(payload, dict) else [])
            records = [r for item in items[:query.limit] if isinstance(item, dict) and (r := self._map(item, exact=exact))]
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found": len(records)})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"Charity Commission HTTP {exc.response.status_code}", metadata={"retryable": retryable})

    def _map(self, item: dict, *, exact: bool) -> RemoteSourceRecord | None:
        org = str(item.get("organisation_number") or "").strip()
        reg = str(item.get("reg_charity_number") or "").strip()
        name = str(item.get("charity_name") or "").strip()
        if not name or not (org or reg):
            return None
        rid = org or reg
        return RemoteSourceRecord(source=self.source_code, record_id=rid, record_type="charity", display_name=name, country="GB", source_url=f"https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{org}" if org else None, identifiers={k:v for k,v in {"ORGANISATION_NUMBER":org,"CHARITY_NUMBER":reg}.items() if v}, attributes={"candidate_only": not exact, "identity_confirmed": exact, "registration_status": item.get("reg_status"), "registered_at": item.get("date_of_registration"), "removed_at": item.get("date_of_removal"), "group_subsidiary_suffix": item.get("group_subsid_suffix")})
