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


class SamGovEntityAdapter(RemoteSourceAdapter):
    URL = "https://api.sam.gov/entity-information/v4/entities"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: JsonHttpClient | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = client or JsonHttpClient()

    @property
    def source_code(self) -> str:
        return "us_sam_entities"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"uei", "registration_id", "company_name", "entity"})

    @property
    def global_scope(self) -> bool:
        # SAM contains both U.S. and foreign registrants.
        return True

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.configured:
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.NOT_CONFIGURED,
                error="SAM_GOV_API_KEY is not configured.",
            )

        params: dict[str, str | int] = {
            "api_key": self.api_key or "",
            "includeSections": "entityRegistration,coreData",
            "size": min(query.limit, 10),
        }
        if query.capability in {"uei", "registration_id"}:
            uei = re.sub(r"\s+", "", query.value).upper()
            if not re.fullmatch(r"[A-Z0-9]{12}", uei):
                return RemoteAdapterResult(
                    self.source_code,
                    RemoteAdapterStatus.NOT_SUPPORTED,
                    error="SAM UEI must contain 12 alphanumeric characters.",
                )
            params["ueiSAM"] = uei
        else:
            params["legalBusinessName"] = query.value

        try:
            payload = self.client.get_json(self.URL, params=params, timeout=query.timeout)
            items = payload.get("entityData", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                raise ValueError("Malformed SAM.gov entity response.")
            records = [
                r for item in items[: query.limit]
                if isinstance(item, dict) and (r := self._map(item)) is not None
            ]
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "public_sections_only": True,
                    "cui_requested": False,
                },
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            retryable = code == 429 or code >= 500
            return RemoteAdapterResult(
                self.source_code,
                RemoteAdapterStatus.PARTIAL if retryable else RemoteAdapterStatus.FAILED,
                error=f"SAM.gov HTTP {code}",
                metadata={
                    "retryable": retryable,
                    "rate_limited": code == 429,
                    "credentials_invalid_or_forbidden": code in {401, 403},
                },
            )

    def _map(self, item: dict) -> RemoteSourceRecord | None:
        registration = item.get("entityRegistration") or {}
        if not isinstance(registration, dict):
            return None
        uei = str(registration.get("ueiSAM") or "").strip()
        name = str(registration.get("legalBusinessName") or "").strip()
        if not uei or not name:
            return None

        core = item.get("coreData") or {}
        if not isinstance(core, dict):
            core = {}
        address = core.get("physicalAddress") or {}
        if not isinstance(address, dict):
            address = {}
        country = str(address.get("countryCode") or "").strip().upper() or None
        if country and len(country) != 2:
            country = None

        return RemoteSourceRecord(
            source=self.source_code,
            record_id=uei,
            record_type="sam_entity",
            display_name=name,
            country=country,
            source_url=f"https://sam.gov/entity/{uei}/coreData",
            identifiers={
                "UEI": uei,
                **({"CAGE": str(registration.get("cageCode"))} if registration.get("cageCode") else {}),
            },
            attributes={
                "dba_name": registration.get("dbaName"),
                "registration_status": registration.get("registrationStatus"),
                "registration_date": registration.get("registrationDate"),
                "expiration_date": registration.get("registrationExpirationDate"),
                "purpose_of_registration": registration.get("purposeOfRegistrationDesc"),
                "physical_address": address,
                "public_display_flag": registration.get("publicDisplayFlag"),
                "exclusion_status_flag": registration.get("exclusionStatusFlag"),
                "public_sections_only": True,
                "cui_included": False,
            },
        )
