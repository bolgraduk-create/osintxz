from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

def _first(root: ET.Element, *names: str) -> str | None:
    wanted=set(names)
    for node in root.iter():
        if _local(node.tag) in wanted and node.text and node.text.strip():
            return node.text.strip()
    return None

def _all(root: ET.Element, name: str) -> list[str]:
    return [n.text.strip() for n in root.iter() if _local(n.tag)==name and n.text and n.text.strip()]


class AustraliaAbnLookupAdapter(RemoteSourceAdapter):
    BASE = "https://abr.business.gov.au/abrxmlsearch/AbrXmlSearch.asmx"
    MAX_BYTES = 4_000_000

    def __init__(self, *, authentication_guid: str | None = None, transport=None) -> None:
        self.authentication_guid=(authentication_guid or "").strip() or None
        self.transport=transport

    @property
    def source_code(self) -> str: return "au_abn_lookup"
    @property
    def configured(self) -> bool: return self.authentication_guid is not None
    @property
    def capabilities(self) -> frozenset[str]: return frozenset({"abn","company_name","organization","name"})
    @property
    def countries(self) -> frozenset[str]: return frozenset({"AU"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.authentication_guid:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_CONFIGURED, error="ABN_LOOKUP_GUID is not configured.")
        try:
            if query.capability == "abn":
                abn=re.sub(r"\s+", "", query.value)
                if not re.fullmatch(r"\d{11}", abn):
                    return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="ABN must contain 11 digits.")
                root=self._get("SearchByABNv202001", {"searchString":abn,"includeHistoricalDetails":"N","authenticationGuid":self.authentication_guid}, query.timeout)
                entity=next((n for n in root.iter() if _local(n.tag).startswith("businessEntity")), root)
                record=self._map_entity(entity)
                records=[record] if record else []
            else:
                params={
                    "name":query.value,"postcode":"","legalName":"Y","tradingName":"Y","businessName":"Y","activeABNsOnly":"N",
                    "NSW":"Y","SA":"Y","ACT":"Y","VIC":"Y","WA":"Y","NT":"Y","QLD":"Y","TAS":"Y",
                    "authenticationGuid":self.authentication_guid,"searchWidth":"typical","minimumScore":"70","maxSearchResults":str(min(query.limit,20)),
                }
                root=self._get("ABRSearchByNameAdvancedSimpleProtocol2017", params, query.timeout)
                records=[]
                for node in root.iter():
                    if _local(node.tag)=="searchResultsRecord":
                        r=self._map_search(node)
                        if r: records.append(r)
                records=records[:query.limit]
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found":len(records),"official":True})
        except httpx.HTTPStatusError as exc:
            retryable=exc.response.status_code==429 or exc.response.status_code>=500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"ABN Lookup HTTP {exc.response.status_code}", metadata={"retryable":retryable})
        except (ET.ParseError, ValueError) as exc:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.FAILED, error=str(exc), metadata={"failure_isolated":True})

    def _get(self, method: str, params: dict[str,str], timeout: int) -> ET.Element:
        with httpx.Client(timeout=httpx.Timeout(float(timeout)), transport=self.transport, follow_redirects=False, headers={"User-Agent":"OSINTXZ/1.0 RemoteAdapters","Accept":"text/xml"}) as client:
            with client.stream("GET", f"{self.BASE}/{method}", params=params, headers={"Accept-Encoding":"identity"}) as response:
                body=bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(body)+len(chunk)>self.MAX_BYTES: raise ValueError("ABN Lookup response exceeds limit.")
                    body.extend(chunk)
                response.raise_for_status()
        return ET.fromstring(bytes(body))

    def _map_entity(self, root: ET.Element) -> RemoteSourceRecord | None:
        abn=_first(root,"identifierValue") or _first(root,"ABN")
        name=_first(root,"organisationName","fullName")
        if not abn or not name: return None
        state=_first(root,"stateCode"); postcode=_first(root,"postcode")
        return RemoteSourceRecord(source=self.source_code,record_id=abn,record_type="organization",display_name=name,country="AU",source_url=f"https://abr.business.gov.au/ABN/View?id={abn}",identifiers={"ABN":abn},attributes={"status":_first(root,"entityStatusCode"),"entity_type":_first(root,"entityTypeCode","entityDescription"),"state":state,"postcode":postcode,"business_names":_all(root,"organisationName")})

    def _map_search(self, root: ET.Element) -> RemoteSourceRecord | None:
        abn=_first(root,"identifierValue")
        name=_first(root,"organisationName","fullName")
        if not abn or not name: return None
        return RemoteSourceRecord(source=self.source_code,record_id=abn,record_type="organization",display_name=name,country="AU",source_url=f"https://abr.business.gov.au/ABN/View?id={abn}",identifiers={"ABN":abn},attributes={"score":_first(root,"score"),"state":_first(root,"stateCode"),"postcode":_first(root,"postcode")})
