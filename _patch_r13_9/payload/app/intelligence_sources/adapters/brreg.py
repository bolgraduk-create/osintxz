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


class NorwayBrregAdapter(RemoteSourceAdapter):
    BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "no_brreg_entities"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"company_name", "registration_id", "organization", "name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"NO"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability == "registration_id":
                orgnr = re.sub(r"\s+", "", query.value)
                if not re.fullmatch(r"\d{9}", orgnr):
                    return RemoteAdapterResult(
                        self.source_code,
                        RemoteAdapterStatus.NOT_SUPPORTED,
                        error="Norwegian organisation number must contain 9 digits.",
                    )
                payload = self.client.get_json(
                    f"{self.BASE}/{orgnr}",
                    timeout=query.timeout,
                )
                items = [payload]
            else:
                payload = self.client.get_json(
                    self.BASE,
                    params={"navn": query.value, "size": min(query.limit, 100)},
                    timeout=query.timeout,
                )
                embedded = payload.get("_embedded", {}) if isinstance(payload, dict) else {}
                items = embedded.get("enheter", []) if isinstance(embedded, dict) else []
                if not isinstance(items, list):
                    raise ValueError("Malformed BRREG search response.")

            records = [
                r for item in items[: query.limit]
                if isinstance(item, dict)
                and (r := self._map(item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records), "official": True},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"BRREG HTTP {exc.response.status_code}",
                metadata={"retryable": retryable},
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        orgnr = str(item.get("organisasjonsnummer") or "").strip()
        name = str(item.get("navn") or "").strip()
        if not orgnr or not name:
            return None
        form = item.get("organisasjonsform") or {}
        address = item.get("forretningsadresse") or {}
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=orgnr,
            record_type="organization",
            display_name=name,
            country="NO",
            source_url=f"https://data.brreg.no/enhetsregisteret/oppslag/enheter/{orgnr}",
            identifiers={"ORGANISASJONSNUMMER": orgnr},
            attributes={
                "organization_form": form.get("beskrivelse") if isinstance(form, dict) else None,
                "organization_form_code": form.get("kode") if isinstance(form, dict) else None,
                "employees": item.get("antallAnsatte"),
                "website": item.get("hjemmeside"),
                "bankrupt": item.get("konkurs"),
                "under_liquidation": item.get("underAvvikling"),
                "address": address,
                "historical_names": item.get("historiskeNavn", []),
            },
        )
