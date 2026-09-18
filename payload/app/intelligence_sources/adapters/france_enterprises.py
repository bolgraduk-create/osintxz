from __future__ import annotations

import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class FranceEnterpriseSearchAdapter(RemoteSourceAdapter):
    BASE = "https://recherche-entreprises.api.gouv.fr/search"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "fr_sirene"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"siren", "siret", "company_name", "organization", "name", "establishment"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"FR"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        value = re.sub(r"\s+", "", query.value) if query.capability in {"siren", "siret"} else query.value.strip()
        if query.capability == "siren" and not re.fullmatch(r"\d{9}", value):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="SIREN must contain 9 digits.")
        if query.capability == "siret" and not re.fullmatch(r"\d{14}", value):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="SIRET must contain 14 digits.")
        try:
            payload = self.client.get_json(self.BASE, params={"q": value, "page": 1, "per_page": min(query.limit, 25)}, timeout=query.timeout)
            items = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                raise ValueError("Malformed France enterprise response.")
            records = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if query.capability == "siren" and str(item.get("siren") or "") != value:
                    continue
                if query.capability == "siret" and not self._contains_siret(item, value):
                    continue
                record = self._map(item, exact=query.capability in {"siren", "siret"})
                if record:
                    records.append(record)
                if len(records) >= query.limit:
                    break
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found": len(records), "official_open_api": True})
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"France Enterprise API HTTP {exc.response.status_code}", metadata={"retryable": retryable})

    @staticmethod
    def _contains_siret(item: dict, siret: str) -> bool:
        siege = item.get("siege") or {}
        if isinstance(siege, dict) and str(siege.get("siret") or "") == siret:
            return True
        for row in item.get("matching_etablissements") or []:
            if isinstance(row, dict) and str(row.get("siret") or "") == siret:
                return True
        return False

    def _map(self, item: dict, *, exact: bool) -> RemoteSourceRecord | None:
        siren = str(item.get("siren") or "").strip()
        name = str(item.get("nom_complet") or item.get("nom_raison_sociale") or "").strip()
        if not siren or not name:
            return None
        siege = item.get("siege") if isinstance(item.get("siege"), dict) else {}
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=siren,
            record_type="organization",
            display_name=name,
            country="FR",
            source_url=f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}",
            identifiers={k: v for k, v in {"SIREN": siren, "SIRET": str(siege.get("siret") or "").strip()}.items() if v},
            attributes={
                "candidate_only": not exact,
                "identity_confirmed": exact,
                "legal_form": item.get("nature_juridique"),
                "main_activity": item.get("activite_principale"),
                "employee_band": item.get("tranche_effectif_salarie"),
                "status": item.get("etat_administratif"),
                "head_office": siege,
            },
        )
