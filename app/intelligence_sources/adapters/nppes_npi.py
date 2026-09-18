from __future__ import annotations

import re
from typing import Any

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import PublicJsonClient


_NPI = re.compile(r"^\d{10}$")


class NppesNpiAdapter(RemoteSourceAdapter):
    API = "https://npiregistry.cms.hhs.gov/api/"

    def __init__(self, *, transport=None) -> None:
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 NPPESPublicRegistry",
        )

    @property
    def source_code(self) -> str:
        return "us_nppes_npi"

    @property
    def countries(self) -> frozenset[str]:
        return frozenset({"US"})

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "npi",
            "provider",
            "person",
            "organization",
            "name",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        specs = self._specs(query)
        records: list[RemoteSourceRecord] = []
        seen: set[str] = set()
        errors: list[str] = []
        retryable = False

        for params in specs:
            params = {
                "version": "2.1",
                "limit": min(query.limit, 200),
                "skip": 0,
                **params,
            }
            try:
                payload = self.client.request_json(
                    "GET",
                    self.API,
                    params=params,
                    timeout=query.timeout,
                )
            except httpx.HTTPStatusError as exc:
                errors.append(f"HTTP {exc.response.status_code}")
                retryable = retryable or (
                    exc.response.status_code == 429
                    or exc.response.status_code >= 500
                )
                continue
            except Exception as exc:
                errors.append(str(exc))
                continue

            rows = payload.get("results", []) if isinstance(payload, dict) else []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                record = self._record(row, exact=bool(_NPI.fullmatch(query.value)))
                if record is None or record.record_id in seen:
                    continue
                seen.add(record.record_id)
                records.append(record)
                if len(records) >= query.limit:
                    break
            if len(records) >= query.limit:
                break

        status = RemoteAdapterStatus.SUCCESS
        if errors and records:
            status = RemoteAdapterStatus.PARTIAL
        elif errors and not records:
            status = RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED

        return RemoteAdapterResult(
            source=self.source_code,
            status=status,
            records=records[: query.limit],
            error="; ".join(errors) if errors else None,
            metadata={
                "records_found": len(records[: query.limit]),
                "api_version": "2.1",
                "bulk_query_not_used": True,
                "licensure_validation": False,
            },
        )

    def _specs(self, query: RemoteSourceQuery) -> list[dict[str, Any]]:
        value = query.value.strip()
        if query.capability == "npi" or _NPI.fullmatch(value):
            return [{"number": value}]
        if query.capability == "organization":
            return [{
                "enumeration_type": "NPI-2",
                "organization_name": value,
            }]
        if query.capability == "person":
            return [self._person_params(value)]
        if query.capability in {"provider", "name"}:
            return [
                self._person_params(value),
                {
                    "enumeration_type": "NPI-2",
                    "organization_name": value,
                },
            ]
        return [self._person_params(value)]

    @staticmethod
    def _person_params(value: str) -> dict[str, Any]:
        parts = [part for part in value.split() if part]
        if len(parts) >= 2:
            return {
                "enumeration_type": "NPI-1",
                "first_name": parts[0],
                "last_name": parts[-1],
                "use_first_name_alias": "True",
            }
        return {
            "enumeration_type": "NPI-1",
            "last_name": value,
            "use_first_name_alias": "True",
        }

    @staticmethod
    def _record(row: dict[str, Any], *, exact: bool) -> RemoteSourceRecord | None:
        npi = str(row.get("number") or "").strip()
        if not _NPI.fullmatch(npi):
            return None
        basic = row.get("basic") if isinstance(row.get("basic"), dict) else {}
        enumeration_type = str(row.get("enumeration_type") or "").strip()
        if enumeration_type == "NPI-2":
            display = str(
                basic.get("organization_name")
                or basic.get("name")
                or npi
            ).strip()
            record_type = "npi_organization"
        else:
            parts = [
                basic.get("first_name"),
                basic.get("middle_name"),
                basic.get("last_name"),
                basic.get("credential"),
            ]
            display = " ".join(str(x).strip() for x in parts if str(x or "").strip())
            display = display or npi
            record_type = "npi_individual"

        addresses = []
        for item in row.get("addresses") or []:
            if not isinstance(item, dict):
                continue
            addresses.append({
                "purpose": item.get("address_purpose"),
                "type": item.get("address_type"),
                "address_1": item.get("address_1"),
                "address_2": item.get("address_2"),
                "city": item.get("city"),
                "state": item.get("state"),
                "postal_code": item.get("postal_code"),
                "country_code": item.get("country_code"),
                "telephone_number": item.get("telephone_number"),
            })
            if len(addresses) >= 5:
                break

        taxonomies = []
        for item in row.get("taxonomies") or []:
            if not isinstance(item, dict):
                continue
            taxonomies.append({
                "code": item.get("code"),
                "desc": item.get("desc"),
                "primary": item.get("primary"),
                "state": item.get("state"),
                "license": item.get("license"),
            })
            if len(taxonomies) >= 10:
                break

        return RemoteSourceRecord(
            source="us_nppes_npi",
            record_id=npi,
            record_type=record_type,
            display_name=display,
            source_url="https://npiregistry.cms.hhs.gov/",
            country="US",
            identifiers={"NPI": npi},
            attributes={
                "enumeration_type": enumeration_type,
                "status": basic.get("status"),
                "enumeration_date": basic.get("enumeration_date"),
                "last_updated": basic.get("last_updated"),
                "gender": basic.get("gender"),
                "addresses": addresses,
                "taxonomies": taxonomies,
                "candidate_only": not exact,
                "identity_inference_prohibited": not exact,
                "exact_identifier": exact,
                "licensure_validation": False,
                "public_sensitive": True,
            },
        )
