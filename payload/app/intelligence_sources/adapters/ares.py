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


class CzechAresAdapter(RemoteSourceAdapter):
    BASE = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "cz_ares"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"registration_id", "organization", "company_name", "name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"CZ"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        # This first active ARES adapter intentionally uses the stable exact-ICO
        # endpoint. Name search remains cataloged until its POST search contract
        # is added and tested separately.
        if query.capability != "registration_id":
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="ARES Pack 1 supports exact ICO lookup only.",
            )

        ico = re.sub(r"\s+", "", query.value)
        if not re.fullmatch(r"\d{8}", ico):
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_SUPPORTED,
                error="Czech ICO must contain 8 digits.",
            )

        try:
            item = self.client.get_json(
                f"{self.BASE}/ekonomicke-subjekty/{ico}",
                timeout=query.timeout,
            )
            record = self._map(item)
            if record is None:
                raise ValueError("Malformed ARES entity response.")
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={"records_found": 1, "official": True},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"ARES HTTP {exc.response.status_code}",
                metadata={"retryable": retryable},
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        if not isinstance(item, dict):
            return None
        ico = str(item.get("ico") or "").strip()
        name = str(item.get("obchodniJmeno") or "").strip()
        if not ico or not name:
            return None
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=ico,
            record_type="organization",
            display_name=name,
            country="CZ",
            source_url=f"https://ares.gov.cz/ekonomicke-subjekty?ico={ico}",
            identifiers={"ICO": ico},
            attributes={
                "legal_form": item.get("pravniForma"),
                "tax_id": item.get("dic"),
                "registered": item.get("datumVzniku"),
                "deleted": item.get("datumZaniku"),
                "address": item.get("sidlo"),
                "financial_office": item.get("financniUrad"),
            },
        )
