from __future__ import annotations

import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class CanadaFederalCorporationsAdapter(RemoteSourceAdapter):
    BASE="https://apigateway-passerelledapi.ised-isde.canada.ca/corporations/api/v1/corporations"

    def __init__(self, *, api_key: str | None = None, client: JsonHttpClient | None = None) -> None:
        self.api_key=(api_key or "").strip() or None
        self.client=client or JsonHttpClient()

    @property
    def source_code(self)->str: return "ca_federal_corporations"
    @property
    def configured(self)->bool: return self.api_key is not None
    @property
    def capabilities(self)->frozenset[str]: return frozenset({"corporation_id","business_number","registration_id"})
    @property
    def countries(self)->frozenset[str]: return frozenset({"CA"})

    def search(self, query: RemoteSourceQuery)->RemoteAdapterResult:
        if not self.api_key:
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_CONFIGURED,error="CANADA_CORPORATIONS_API_KEY is not configured.")
        value=re.sub(r"[\s-]+","",query.value)
        if query.capability=="business_number":
            if not re.fullmatch(r"\d{9}",value): return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED,error="Canadian business number must contain 9 digits.")
        elif query.capability in {"corporation_id","registration_id"}:
            if not re.fullmatch(r"\d{1,9}",value): return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED,error="Corporation number must be numeric.")
        else:
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED,error="Corporations Canada API supports exact corporation/business numbers in Pack 3.")
        try:
            payload=self.client.get_json(f"{self.BASE}/{value}.json",params={"lang":"eng"},timeout=query.timeout,headers={"user-key":self.api_key})
            item=None
            if isinstance(payload,list):
                item=next((x for x in payload if isinstance(x,dict)),None)
            elif isinstance(payload,dict): item=payload
            if item is None:
                return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.SUCCESS,records=[])
            record=self._map(item)
            if record is None: raise ValueError("Malformed Corporations Canada response.")
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.SUCCESS,records=[record],metadata={"official":True})
        except httpx.HTTPStatusError as exc:
            retryable=exc.response.status_code==429 or exc.response.status_code>=500
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,error=f"Corporations Canada HTTP {exc.response.status_code}",metadata={"retryable":retryable})

    def _map(self,item:dict)->RemoteSourceRecord|None:
        cid=str(item.get("corporationId") or "").strip()
        names=item.get("corporationNames") or []
        name=""
        historical=[]
        for wrapper in names:
            if not isinstance(wrapper,dict): continue
            n=wrapper.get("CorporationName") or wrapper.get("corporationName") or wrapper
            if not isinstance(n,dict): continue
            val=str(n.get("name") or "").strip()
            if not val: continue
            if n.get("current") is True and not name: name=val
            else: historical.append(val)
        if not name and historical: name=historical[0]
        if not cid or not name: return None
        bn=item.get("businessNumbers")
        if isinstance(bn,dict): bn=str(bn.get("businessNumber") or "").strip()
        else: bn=""
        ids={"CORPORATION_ID":cid}
        if bn: ids["BUSINESS_NUMBER"]=bn
        return RemoteSourceRecord(source=self.source_code,record_id=cid,record_type="organization",display_name=name,country="CA",source_url=f"https://ised-isde.canada.ca/cc/lgcy/fdrlCrpDtls.html?corpId={cid}",identifiers=ids,attributes={"status":item.get("status"),"act":item.get("act"),"addresses":item.get("adresses"),"annual_returns":item.get("annualReturns"),"activities":item.get("activities"),"historical_names":historical})
