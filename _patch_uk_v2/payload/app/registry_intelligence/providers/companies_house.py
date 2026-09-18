from __future__ import annotations

import re

import httpx

from app.infrastructure.registries.companies_house_client import (
    CompaniesHouseCredentialsError,
)
from app.registry_intelligence.contracts import (
    RegistryAccessMode,
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderInfo,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.provider import RegistryProvider


class CompaniesHouseRegistryProvider(RegistryProvider):
    """Official UK Companies House company-search provider."""

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="uk_companies_house",
            display_name="UK Companies House",
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset(
                {
                    RegistryQueryKind.NAME,
                    RegistryQueryKind.REGISTRATION_ID,
                }
            ),
            countries=frozenset({"GB"}),
            global_scope=False,
            public_data_only=True,
            requires_credentials=not self.client.configured,
            default_enabled=True,
            priority=15,
            access_mode=RegistryAccessMode.API,
            source_type=RegistrySourceType.OFFICIAL_API,
            trust_score=0.98,
        )

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported Companies House query.",
            )

        if not self.client.configured:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Companies House API key is not configured.",
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )

        try:
            if query.kind is RegistryQueryKind.REGISTRATION_ID:
                company_number = self._normalize_company_number(
                    query.value
                )
                payload = self.client.get_company_profile(
                    company_number,
                    timeout=query.timeout,
                )
                record = self._profile_to_record(payload)
                if (
                    record is None
                    or (record.registration_id or "").upper()
                    != company_number
                ):
                    return RegistryProviderResult(
                        provider=self.info.name,
                        status=RegistryResultStatus.FAILED,
                        error=(
                            "Malformed Companies House profile response."
                        ),
                        metadata={"failure_isolated": True},
                    )
                records = [record]
            else:
                payload = self.client.search_companies(
                    query.value,
                    limit=query.limit,
                    timeout=query.timeout,
                )
                records = [
                    record
                    for item in self._search_items(payload)
                    if (
                        record := self._search_item_to_record(item)
                    )
                    is not None
                ][: query.limit]

            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "public_data_only": True,
                    "credentials_required": True,
                    "credentials_configured": True,
                    "official_registry": True,
                    "rate_limit_window_seconds": 300,
                    "rate_limit_requests": 600,
                },
            )

        except ValueError as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
            )
        except CompaniesHouseCredentialsError as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            if status_code == 404:
                return RegistryProviderResult(
                    provider=self.info.name,
                    status=RegistryResultStatus.SUCCESS,
                    records=[],
                    metadata={"records_found": 0},
                )

            if status_code in {401, 403}:
                return RegistryProviderResult(
                    provider=self.info.name,
                    status=RegistryResultStatus.FAILED,
                    error=(
                        "Companies House credentials were rejected "
                        f"(HTTP {status_code})."
                    ),
                    metadata={
                        "failure_isolated": True,
                        "credentials_invalid": True,
                        "retryable": False,
                    },
                )

            retryable = status_code == 429 or status_code >= 500
            return RegistryProviderResult(
                provider=self.info.name,
                status=(
                    RegistryResultStatus.PARTIAL
                    if retryable
                    else RegistryResultStatus.FAILED
                ),
                error=f"Companies House HTTP {status_code}.",
                metadata={
                    "failure_isolated": True,
                    "retryable": retryable,
                    "rate_limited": status_code == 429,
                },
            )
        except httpx.RequestError as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.PARTIAL,
                error=str(exc),
                metadata={
                    "failure_isolated": True,
                    "retryable": True,
                },
            )
        except Exception as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

    @staticmethod
    def _normalize_company_number(value: str) -> str:
        number = re.sub(r"\s+", "", value.strip().upper())
        if (
            not number
            or not number.isalnum()
            or not 5 <= len(number) <= 10
        ):
            raise ValueError("Malformed UK company number.")
        return number

    @staticmethod
    def _search_items(payload: dict) -> list[dict]:
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError(
                "Malformed Companies House search response."
            )
        return [item for item in items if isinstance(item, dict)]

    def _profile_to_record(
        self,
        profile: dict,
    ) -> RegistryRecord | None:
        name = str(profile.get("company_name") or "").strip()
        number = str(profile.get("company_number") or "").strip().upper()
        if not name or not number:
            return None

        previous_names = profile.get("previous_company_names")
        if not isinstance(previous_names, list):
            previous_names = []

        sic_codes = profile.get("sic_codes")
        if not isinstance(sic_codes, list):
            sic_codes = []

        return RegistryRecord(
            provider=self.info.name,
            domain=RegistryDomain.BUSINESS,
            record_id=number,
            display_name=name,
            country="GB",
            jurisdiction="GB",
            status=(
                str(profile.get("company_status") or "").strip()
                or None
            ),
            registration_id=number,
            legal_form=(
                str(profile.get("type") or "").strip()
                or None
            ),
            legal_address=self._format_address(
                profile.get("registered_office_address")
            ),
            source_url=self._public_company_url(number),
            confidence=0.99,
            reliability=0.98,
            identifiers={"REGISTRATION_ID": number},
            metadata={
                "official_registry": "UK Companies House",
                "date_of_creation": profile.get("date_of_creation"),
                "date_of_cessation": profile.get("date_of_cessation"),
                "company_status_detail": profile.get(
                    "company_status_detail"
                ),
                "sic_codes": [
                    str(code)
                    for code in sic_codes
                    if str(code).strip()
                ],
                "previous_company_names": [
                    item
                    for item in previous_names
                    if isinstance(item, dict)
                ],
                "registered_office_is_in_dispute": profile.get(
                    "registered_office_is_in_dispute"
                ),
                "undeliverable_registered_office_address": profile.get(
                    "undeliverable_registered_office_address"
                ),
                "partial_data_available": profile.get(
                    "partial_data_available"
                ),
                "accounts": (
                    profile.get("accounts")
                    if isinstance(profile.get("accounts"), dict)
                    else None
                ),
                "confirmation_statement": (
                    profile.get("confirmation_statement")
                    if isinstance(
                        profile.get("confirmation_statement"),
                        dict,
                    )
                    else None
                ),
            },
            entity_kind=RegistryEntityKind.COMPANY,
            source_type=RegistrySourceType.OFFICIAL_API,
            trust_score=0.98,
            raw_reference=number,
        )

    def _search_item_to_record(
        self,
        item: dict,
    ) -> RegistryRecord | None:
        name = str(
            item.get("title")
            or item.get("company_name")
            or ""
        ).strip()
        number = str(
            item.get("company_number") or ""
        ).strip().upper()

        if not name or not number:
            return None

        address = self._format_address(item.get("address"))
        if address is None:
            address = (
                str(item.get("address_snippet") or "").strip()
                or None
            )

        return RegistryRecord(
            provider=self.info.name,
            domain=RegistryDomain.BUSINESS,
            record_id=number,
            display_name=name,
            country="GB",
            jurisdiction="GB",
            status=(
                str(item.get("company_status") or "").strip()
                or None
            ),
            registration_id=number,
            legal_form=(
                str(item.get("company_type") or "").strip()
                or None
            ),
            legal_address=address,
            source_url=self._public_company_url(number),
            confidence=0.82,
            reliability=0.98,
            identifiers={"REGISTRATION_ID": number},
            metadata={
                "official_registry": "UK Companies House",
                "date_of_creation": item.get("date_of_creation"),
                "date_of_cessation": item.get("date_of_cessation"),
                "description": (
                    str(item.get("description") or "").strip()
                    or None
                ),
                "kind": item.get("kind"),
                "matched_by": "company_name_search",
            },
            entity_kind=RegistryEntityKind.COMPANY,
            source_type=RegistrySourceType.OFFICIAL_API,
            trust_score=0.98,
            raw_reference=number,
        )

    @staticmethod
    def _public_company_url(company_number: str) -> str:
        return (
            "https://find-and-update.company-information.service.gov.uk/"
            f"company/{company_number}"
        )

    @staticmethod
    def _format_address(value) -> str | None:
        if not isinstance(value, dict):
            return None

        parts: list[str] = []
        for key in (
            "care_of",
            "premises",
            "address_line_1",
            "address_line_2",
            "locality",
            "region",
            "postal_code",
            "country",
        ):
            item = str(value.get(key) or "").strip()
            if item:
                parts.append(item)

        return ", ".join(parts) or None
