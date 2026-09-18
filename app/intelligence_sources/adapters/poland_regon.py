from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord

NS="http://CIS/BIR/PUBL/2014/07"
DC="http://CIS/BIR/PUBL/2014/07/DataContract"
SOAP="http://www.w3.org/2003/05/soap-envelope"


def _local(tag:str)->str: return tag.rsplit("}",1)[-1]
def _first(root:ET.Element,*names:str)->str|None:
    wanted=set(names)
    for n in root.iter():
        if _local(n.tag) in wanted and n.text and n.text.strip(): return n.text.strip()
    return None


class PolandRegonAdapter(RemoteSourceAdapter):
    ENDPOINT="https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc"
    MAX_BYTES=4_000_000

    def __init__(self, *, user_key:str|None=None, transport=None)->None:
        self.user_key=(user_key or "").strip() or None
        self.transport=transport
    @property
    def source_code(self)->str: return "pl_regon"
    @property
    def configured(self)->bool: return self.user_key is not None
    @property
    def capabilities(self)->frozenset[str]: return frozenset({"regon","nip","krs","registration_id"})
    @property
    def countries(self)->frozenset[str]: return frozenset({"PL"})

    def search(self,query:RemoteSourceQuery)->RemoteAdapterResult:
        if not self.user_key: return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_CONFIGURED,error="POLAND_REGON_API_KEY is not configured.")
        field={"regon":"Regon","nip":"Nip","krs":"Krs","registration_id":"Krs"}.get(query.capability)
        if field is None: return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED)
        value=re.sub(r"[\s-]+","",query.value)
        patterns={"Regon":r"\d{9}|\d{14}","Nip":r"\d{10}","Krs":r"\d{1,10}"}
        if not re.fullmatch(patterns[field],value): return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.NOT_SUPPORTED,error=f"Malformed REGON BIR {field} identifier.")
        try:
            sid=self._login(query.timeout)
            rows=self._search(sid,field,value,query.timeout)
            records=[r for row in rows[:query.limit] if (r:=self._map(row)) is not None]
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.SUCCESS,records=records,metadata={"records_found":len(records),"official":True})
        except httpx.HTTPStatusError as exc:
            retryable=exc.response.status_code==429 or exc.response.status_code>=500
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,error=f"REGON HTTP {exc.response.status_code}",metadata={"retryable":retryable})
        except (ValueError,ET.ParseError) as exc:
            return RemoteAdapterResult(self.source_code,RemoteAdapterStatus.FAILED,error=str(exc),metadata={"failure_isolated":True})

    def _login(self,timeout:int)->str:
        body=f'''<soap:Envelope xmlns:soap="{SOAP}" xmlns:ns="{NS}"><soap:Header/><soap:Body><ns:Zaloguj><ns:pKluczUzytkownika>{html.escape(self.user_key or '')}</ns:pKluczUzytkownika></ns:Zaloguj></soap:Body></soap:Envelope>'''
        root=self._post(body,f"{NS}/IUslugaBIRzewnPubl/Zaloguj",timeout)
        sid=_first(root,"ZalogujResult")
        if not sid: raise ValueError("REGON login did not return a session id.")
        return sid

    def _search(self,sid:str,field:str,value:str,timeout:int)->list[ET.Element]:
        body=f'''<soap:Envelope xmlns:soap="{SOAP}" xmlns:ns="{NS}" xmlns:dc="{DC}"><soap:Header><ns:sid>{html.escape(sid)}</ns:sid></soap:Header><soap:Body><ns:DaneSzukajPodmioty><ns:pParametryWyszukiwania><dc:{field}>{html.escape(value)}</dc:{field}></ns:pParametryWyszukiwania></ns:DaneSzukajPodmioty></soap:Body></soap:Envelope>'''
        root=self._post(body,f"{NS}/IUslugaBIRzewnPubl/DaneSzukajPodmioty",timeout)
        text=_first(root,"DaneSzukajPodmiotyResult")
        if text is None: return []
        inner=ET.fromstring(html.unescape(text).strip())
        return [n for n in inner.iter() if _local(n.tag)=="dane"]

    def _post(self,body:str,action:str,timeout:int)->ET.Element:
        headers={"Content-Type":"application/soap+xml; charset=utf-8","SOAPAction":action,"User-Agent":"OSINTXZ/1.0 RemoteAdapters","Accept":"application/soap+xml"}
        with httpx.Client(timeout=httpx.Timeout(float(timeout)),transport=self.transport,follow_redirects=False,headers=headers) as client:
            with client.stream("POST",self.ENDPOINT,content=body.encode("utf-8"),headers={"Accept-Encoding":"identity"}) as response:
                raw=bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(raw)+len(chunk)>self.MAX_BYTES: raise ValueError("REGON response exceeds limit.")
                    raw.extend(chunk)
                response.raise_for_status()
        return ET.fromstring(bytes(raw))

    def _map(self,row:ET.Element)->RemoteSourceRecord|None:
        regon=_first(row,"Regon") or ""; name=_first(row,"Nazwa") or ""
        if not regon or not name: return None
        nip=_first(row,"Nip"); krs=_first(row,"Krs")
        ids={"REGON":regon}
        if nip: ids["NIP"]=nip
        if krs: ids["KRS"]=krs
        return RemoteSourceRecord(source=self.source_code,record_id=regon,record_type="organization",display_name=name,country="PL",source_url="https://wyszukiwarkaregon.stat.gov.pl/appBIR/index.aspx",identifiers=ids,attributes={"province":_first(row,"Wojewodztwo"),"county":_first(row,"Powiat"),"municipality":_first(row,"Gmina"),"city":_first(row,"Miejscowosc"),"postcode":_first(row,"KodPocztowy"),"street":_first(row,"Ulica"),"type":_first(row,"Typ")})
