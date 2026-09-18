from __future__ import annotations

import re
import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterResult, RemoteAdapterStatus, RemoteSourceQuery, RemoteSourceRecord


class FranceEnterpriseSearchAdapter(RemoteSourceAdapter):
    """Open DINUM company search backed by public French administrative data (incl. SIRENE/RNE)."""

    BASE = "https://recherche-entreprises.api.gouv.fr/search"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "fr_sirene"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"siren", "siret", "company_name", "organization", "name"})

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"FR"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if query.capability == "siren" and not re.fullmatch(r"\d{9}", re.sub(r"\s+", "", query.value)):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="SIREN must contain 9 digits.")
        if query.capability == "siret" and not re.fullmatch(r"\d{14}", re.sub(r"\s+", "", query.value)):
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.NOT_SUPPORTED, error="SIRET must contain 14 digits.")

        value = re.sub(r"\s+", "", query.value) if query.capability in {"siren", "siret"} else query.value
        try:
            payload = self.client.get_json(
                self.BASE,
                params={"q": value, "page": 1, "per_page": min(query.limit, 25)},
                timeout=query.timeout,
            )
            items = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                raise ValueError("Malformed French company-search response.")
            records=[]
            for item in items[:query.limit]:
                if not isinstance(item, dict):
                    continue
                record=self._map(item)
                if record is None:
                    continue
                if query.capability == "siren" and record.identifiers.get("SIREN") != value:
                    continue
                if query.capability == "siret" and record.identifiers.get("SIRET") != value:
                    continue
                records.append(record)
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=records, metadata={"records_found": len(records), "official": True})
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED, error=f"France company API HTTP {exc.response.status_code}", metadata={"retryable": retryable})

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        siren=str(item.get("siren") or "").strip()
        name=str(item.get("nom_complet") or item.get("nom_raison_sociale") or "").strip()
        if not siren or not name:
            return None
        siege=item.get("siege") if isinstance(item.get("siege"), dict) else {}
        siret=str(siege.get("siret") or "").strip()
        identifiers={"SIREN": siren}
        if siret: identifiers["SIRET"] = siret
        address=" ".join(str(siege.get(k) or "").strip() for k in ("numero_voie","type_voie","libelle_voie","code_postal","libelle_commune") if str(siege.get(k) or "").strip())
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=siren,
            record_type="organization",
            display_name=name,
            country="FR",
            source_url=f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}",
            identifiers=identifiers,
            attributes={
                "status": item.get("etat_administratif"),
                "legal_form": item.get("nature_juridique"),
                "activity": item.get("activite_principale"),
                "employees_band": item.get("tranche_effectif_salarie"),
                "establishments": item.get("nombre_etablissements"),
                "open_establishments": item.get("nombre_etablissements_ouverts"),
                "head_office": siege,
                "address": address or None,
            },
        )
