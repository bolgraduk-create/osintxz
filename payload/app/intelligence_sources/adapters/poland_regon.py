from __future__ import annotations

import html
import re
from xml.etree import ElementTree as ET

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class PolandRegonBirAdapter(RemoteSourceAdapter):
    ENDPOINT = "https://wyszukiwarkaregon.stat.gov.pl/wsBIR/UslugaBIRzewnPubl.svc"
    ACTION_BASE = "http://CIS/BIR/PUBL/2014/07/IUslugaBIRzewnPubl"
    NS = "http://CIS/BIR/PUBL/2014/07"
    DATA_NS = "http://CIS/BIR/PUBL/2014/07/DataContract"
    SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
    MAX_BYTES = 4_000_000

    def __init__(self, *, user_key: str | None = None, transport=None) -> None:
        self.user_key = (user_key or "").strip() or None
        self.transport = transport

    @property
    def source_code(self) -> str:
        return "pl_regon"

    @property
    def configured(self) -> bool:
        return self.user_key is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"regon", "nip", "krs", "organization"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"PL"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.user_key:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_CONFIGURED, error="REGON_BIR_USER_KEY is not configured.")
        field = {"regon": "Regon", "nip": "Nip", "krs": "Krs"}.get(query.capability)
        if field is None:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="REGON Pack 3 supports exact REGON/NIP/KRS lookup.")
        value = re.sub(r"\D", "", query.value)
        if query.capability == "regon" and len(value) not in {9, 14}:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="REGON must contain 9 or 14 digits.")
        if query.capability == "nip" and len(value) != 10:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="NIP must contain 10 digits.")
        if query.capability == "krs" and not (1 <= len(value) <= 10):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="KRS must contain up to 10 digits.")
        try:
            sid = self._login(query.timeout)
            if not sid:
                raise ValueError("REGON BIR login returned an empty session ID.")
            rows = self._search(field, value, sid=sid, timeout=query.timeout)
            records = [r for row in rows[:query.limit] if (r := self._map(row)) is not None]
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found": len(records), "identity_confirmed": True})
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"REGON BIR HTTP {exc.response.status_code}", metadata={"retryable": retryable})
        except httpx.RequestError as exc:
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL, error=str(exc), metadata={"retryable": True})

    def _login(self, timeout: int) -> str:
        body = (
            f'<s:Envelope xmlns:s="{self.SOAP_NS}"><s:Body>'
            f'<Zaloguj xmlns="{self.NS}"><pKluczUzytkownika>{html.escape(self.user_key or "")}</pKluczUzytkownika></Zaloguj>'
            f'</s:Body></s:Envelope>'
        )
        text = self._soap("Zaloguj", body, timeout=timeout)
        root = ET.fromstring(text)
        node = next((el for el in root.iter() if el.tag.endswith("ZalogujResult")), None)
        return (node.text or "").strip() if node is not None else ""

    def _search(self, field: str, value: str, *, sid: str, timeout: int) -> list[dict[str, str]]:
        body = (
            f'<s:Envelope xmlns:s="{self.SOAP_NS}" xmlns:bir="{self.NS}" xmlns:dat="{self.DATA_NS}"><s:Body>'
            f'<bir:DaneSzukajPodmioty><bir:pParametryWyszukiwania><dat:{field}>{html.escape(value)}</dat:{field}></bir:pParametryWyszukiwania></bir:DaneSzukajPodmioty>'
            f'</s:Body></s:Envelope>'
        )
        text = self._soap("DaneSzukajPodmioty", body, timeout=timeout, sid=sid)
        root = ET.fromstring(text)
        node = next((el for el in root.iter() if el.tag.endswith("DaneSzukajPodmiotyResult")), None)
        if node is None or not (node.text or "").strip():
            return []
        inner = html.unescape((node.text or "").strip())
        data_root = ET.fromstring(inner)
        rows = []
        for dane in data_root.findall(".//dane"):
            rows.append({child.tag.split("}")[-1]: (child.text or "").strip() for child in list(dane)})
        return rows

    def _soap(self, operation: str, body: str, *, timeout: int, sid: str | None = None) -> str:
        headers = {
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{self.ACTION_BASE}/{operation}"',
            "User-Agent": "OSINTXZ/1.0 REGON-BIR",
            "Accept-Encoding": "identity",
        }
        if sid:
            headers["sid"] = sid
        with httpx.Client(timeout=httpx.Timeout(float(timeout)), transport=self.transport, follow_redirects=False) as client:
            response = client.post(self.ENDPOINT, content=body.encode("utf-8"), headers=headers)
            response.raise_for_status()
            if len(response.content) > self.MAX_BYTES:
                raise ValueError("REGON BIR response exceeds limit.")
            return response.text

    def _map(self, row: dict[str, str]) -> RemoteSourceRecord | None:
        regon = row.get("Regon", "").strip()
        name = row.get("Nazwa", "").strip()
        if not regon or not name:
            return None
        nip = row.get("Nip", "").strip()
        address = " ".join(filter(None, [row.get("Ulica"), row.get("NrNieruchomosci"), row.get("NrLokalu"), row.get("KodPocztowy"), row.get("Miejscowosc")]))
        return RemoteSourceRecord(source=self.source_code, record_id=regon, record_type="organization", display_name=name, country="PL", identifiers={k:v for k,v in {"REGON":regon,"NIP":nip}.items() if v}, attributes={"identity_confirmed": True, "voivodeship": row.get("Wojewodztwo"), "county": row.get("Powiat"), "municipality": row.get("Gmina"), "address": address or None, "type": row.get("Typ"), "silos_id": row.get("SilosID"), "activity_end_date": row.get("DataZakonczeniaDzialalnosci")})
