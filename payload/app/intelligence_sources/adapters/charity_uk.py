from __future__ import annotations

import re
from urllib.parse import quote
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class UkCharityCommissionAdapter(RemoteSourceAdapter):
    BASE="https://api.charitycommission.gov.uk/register/api"

    def __init__(self, *, api_key: str | None = None, client: JsonHttpClient | None = None) -> None:
        self.api_key=(api_key or "").strip() or None
        self.client=client or JsonHttpClient()

    @property
    def source_code(self)->str: return "uk_charity_commission"
    @property
    def configured(self)->bool: return self.api_key is not None
    @property
    def capabilities(self)->frozenset[str]: return frozenset({"charity_name","charity_number","organization","name"})
    @property
    def countries(self)->frozenset[str]: return frozenset({"GB"})

    def search(self,query:RemoteSourceQuery)->RemoteAdapterResult:
        if not self.api_key:
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_CONFIGURED,error="UK_CHARITY_COMMISSION_API_KEY is not configured.")
        headers={"Ocp-Apim-Subscription-Key":self.api_key,"Cache-Control":"no-cache"}
        try:
            if query.capability=="charity_number":
                number=re.sub(r"\s+","",query.value)
                if not re.fullmatch(r"\d{1,12}",number): return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED,error="Charity number must be numeric.")
                payload=self.client.get_json(f"{self.BASE}/charityRegNumber/{number}/0",timeout=query.timeout,headers=headers)
            else:
                payload=self.client.get_json(f"{self.BASE}/searchCharityName/{quote(query.value,safe='')}",timeout=query.timeout,headers=headers)
            items=self._items(payload)
            records=[r for item in items[:query.limit] if isinstance(item,dict) and (r:=self._map(item)) is not None]
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.SUCCESS,records=records,metadata={"records_found":len(records),"official":True})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code==404: return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.SUCCESS,records=[])
            retryable=exc.response.status_code==429 or exc.response.status_code>=500
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,error=f"Charity Commission HTTP {exc.response.status_code}",metadata={"retryable":retryable})

    @staticmethod
    def _items(payload):
        if isinstance(payload,list): return payload
        if isinstance(payload,dict):
            for key in ("charities","results","items"):
                if isinstance(payload.get(key),list): return payload[key]
            return [payload]
        return []

    def _map(self,item:dict)->RemoteSourceRecord|None:
        number=item.get("reg_charity_number") or item.get("charity_number") or item.get("registered_charity_number") or item.get("registration_number")
        name=item.get("charity_name") or item.get("reg_charity_name") or item.get("organisation_name") or item.get("name")
        number=str(number or "").strip(); name=str(name or "").strip()
        if not number or not name: return None
        return RemoteSourceRecord(source=self.source_code,record_id=number,record_type="charity",display_name=name,country="GB",source_url=f"https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{number}",identifiers={"CHARITY_NUMBER":number},attributes={"status":item.get("status") or item.get("charity_status"),"registration_date":item.get("date_of_registration") or item.get("registration_date"),"removal_date":item.get("date_of_removal"),"activities":item.get("activities"),"raw_public_fields":item})
