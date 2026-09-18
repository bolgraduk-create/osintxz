from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


class RorAdapter(RemoteSourceAdapter):
    BASE = "https://api.ror.org/v2/organizations"

    def __init__(self, *, client: JsonHttpClient | None = None) -> None:
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "ror"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"organization", "ror_id", "affiliation", "name"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        try:
            if query.capability == "ror_id":
                rid = query.value.rstrip("/").split("/")[-1]
                payload = self.client.get_json(
                    f"{self.BASE}/{rid}",
                    timeout=query.timeout,
                )
                items = [payload]
            else:
                params = {"query": query.value}
                if query.country:
                    params["filter"] = f"country.country_code:{query.country}"
                payload = self.client.get_json(
                    self.BASE,
                    params=params,
                    timeout=query.timeout,
                )
                items = payload.get("items", []) if isinstance(payload, dict) else []
                if not isinstance(items, list):
                    raise ValueError("Malformed ROR response.")

            records = [
                r for item in items[: query.limit]
                if isinstance(item, dict)
                and (r := self._map(item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={"records_found": len(records)},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return RemoteAdapterResult(self.source_code, RemoteAdapterStatus.SUCCESS, records=[])
            retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"ROR HTTP {exc.response.status_code}",
                metadata={"retryable": retryable},
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        rid = str(item.get("id") or "").strip()
        if not rid:
            return None

        names = item.get("names") or []
        name = ""
        for entry in names:
            if isinstance(entry, dict) and "ror_display" in (entry.get("types") or []):
                name = str(entry.get("value") or "").strip()
                break
        if not name and names and isinstance(names[0], dict):
            name = str(names[0].get("value") or "").strip()
        if not name:
            return None

        countries = item.get("locations") or []
        country = None
        if countries and isinstance(countries[0], dict):
            details = countries[0].get("geonames_details") or {}
            if isinstance(details, dict):
                country = details.get("country_code")

        return RemoteSourceRecord(
            source=self.source_code,
            record_id=rid,
            record_type="research_organization",
            display_name=name,
            source_url=rid if rid.startswith("http") else None,
            country=str(country).upper() if country else None,
            identifiers={"ROR": rid},
            attributes={
                "status": item.get("status"),
                "types": item.get("types"),
                "domains": item.get("domains"),
                "links": item.get("links"),
                "external_ids": item.get("external_ids"),
                "locations": item.get("locations"),
                "relationships": item.get("relationships"),
            },
        )
