from __future__ import annotations

import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


class SecEdgarAdapter(RemoteSourceAdapter):
    BASE = "https://data.sec.gov/submissions"

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        client: JsonHttpClient | None = None,
    ) -> None:
        self.user_agent = (user_agent or "").strip() or None
        self.client = client or JsonHttpClient(
            user_agent=self.user_agent or "OSINTXZ/1.0"
        )

    @property
    def source_code(self) -> str:
        return "us_sec_edgar"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"cik", "company_filings", "securities"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    @property
    def configured(self) -> bool:
        # SEC asks automated clients to declare an identifying User-Agent.
        return self.user_agent is not None

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        cik_raw = re.sub(r"\s+", "", query.value)
        if not re.fullmatch(r"\d{1,10}", cik_raw):
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="SEC CIK must contain 1 to 10 digits.",
            )
        if not self.configured:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_CONFIGURED,
                error="SEC_EDGAR_USER_AGENT is not configured.",
            )

        cik = cik_raw.zfill(10)
        try:
            item = self.client.get_json(
                f"{self.BASE}/CIK{cik}.json",
                timeout=query.timeout,
                headers={"User-Agent": self.user_agent or ""},
            )
            record = self._map(item, cik=cik, filing_limit=min(query.limit, 25))
            if record is None:
                raise ValueError("Malformed SEC submissions response.")
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={
                    "records_found": 1,
                    "official": True,
                    "bulk_download_used": False,
                    "fair_access_max_requests_per_second": 10,
                },
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 404:
                return RemoteAdapterResult(
                    self.source_code, RemoteAdapterStatus.SUCCESS, records=[]
                )
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"SEC EDGAR HTTP {code}",
                metadata={"retryable": retryable, "rate_limited": code == 429},
            )

    def _map(self, item: dict, *, cik: str, filing_limit: int) -> RemoteSourceRecord | None:
        if not isinstance(item, dict):
            return None
        name = str(item.get("name") or "").strip()
        returned_cik = str(item.get("cik") or cik).strip()
        if not name:
            return None

        recent_out: list[dict] = []
        filings = item.get("filings") or {}
        recent = filings.get("recent") if isinstance(filings, dict) else None
        if isinstance(recent, dict):
            fields = (
                "accessionNumber", "filingDate", "reportDate", "acceptanceDateTime",
                "act", "form", "fileNumber", "filmNumber", "items", "size",
                "isXBRL", "isInlineXBRL", "primaryDocument", "primaryDocDescription",
            )
            lengths = [len(v) for v in recent.values() if isinstance(v, list)]
            rows = min([filing_limit, *lengths]) if lengths else 0
            for idx in range(rows):
                row = {}
                for key in fields:
                    values = recent.get(key)
                    if isinstance(values, list) and idx < len(values):
                        row[key] = values[idx]
                if row:
                    recent_out.append(row)

        return RemoteSourceRecord(
            source=self.source_code,
            record_id=cik,
            record_type="sec_filer",
            display_name=name,
            country="US",
            source_url=f"https://www.sec.gov/edgar/browse/?CIK={cik}",
            identifiers={"CIK": cik},
            attributes={
                "sic": item.get("sic"),
                "sic_description": item.get("sicDescription"),
                "owner_org": item.get("ownerOrg"),
                "tickers": item.get("tickers") or [],
                "exchanges": item.get("exchanges") or [],
                "state_of_incorporation": item.get("stateOfIncorporation"),
                "fiscal_year_end": item.get("fiscalYearEnd"),
                "addresses": item.get("addresses") or {},
                "former_names": item.get("formerNames") or [],
                "recent_filings": recent_out,
                "identity_confirmed": False,
                "identity_note": "SEC filer record; no cross-source identity merge by name alone.",
            },
        )
