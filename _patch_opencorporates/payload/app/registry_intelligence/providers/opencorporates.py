from __future__ import annotations

import httpx

from app.infrastructure.registries.opencorporates_client import (
    OpenCorporatesCredentialsError,
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


class OpenCorporatesRegistryProvider(RegistryProvider):
    """
    Company discovery through OpenCorporates.

    OpenCorporates is an aggregator, not an official registry. Records preserve
    upstream source metadata and are never assigned official-source trust.
    """

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="opencorporates",
            display_name="OpenCorporates",
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset(
                {
                    RegistryQueryKind.NAME,
                    RegistryQueryKind.REGISTRATION_ID,
                }
            ),
            global_scope=True,
            public_data_only=True,
            requires_credentials=not self.client.configured,
            default_enabled=True,
            priority=60,
            access_mode=RegistryAccessMode.API,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.85,
        )

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported OpenCorporates query.",
            )

        if not self.client.configured:
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="OpenCorporates API token is not configured.",
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )

        try:
            payload = self.client.search_companies(
                query.value,
                country=query.country,
                limit=query.limit,
                registration_id_only=(
                    query.kind is RegistryQueryKind.REGISTRATION_ID
                ),
                timeout=query.timeout,
            )

            rows = self._company_rows(payload)
            records = [
                record
                for row in rows
                if (
                    record := self._to_record(
                        row,
                        exact_identifier=(
                            query.kind
                            is RegistryQueryKind.REGISTRATION_ID
                        ),
                    )
                )
                is not None
            ]

            if query.kind is RegistryQueryKind.REGISTRATION_ID:
                requested = query.value.strip().casefold()
                records = [
                    record
                    for record in records
                    if (record.registration_id or "")
                    .strip()
                    .casefold()
                    == requested
                ]

            if query.country:
                requested_country = query.country.strip().upper()
                records = [
                    record
                    for record in records
                    if (record.country or "").upper()
                    == requested_country
                ]

            records = records[: query.limit]
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "public_data_only": True,
                    "credentials_required": True,
                    "credentials_configured": True,
                    "aggregator": True,
                },
            )

        except OpenCorporatesCredentialsError as exc:
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            if status_code in {401, 403}:
                return RegistryProviderResult(
                    provider="opencorporates",
                    status=RegistryResultStatus.FAILED,
                    error=(
                        "OpenCorporates credentials were rejected "
                        f"(HTTP {status_code})."
                    ),
                    metadata={
                        "failure_isolated": True,
                        "credentials_invalid": True,
                        "retryable": False,
                    },
                )

            if status_code == 404:
                return RegistryProviderResult(
                    provider="opencorporates",
                    status=RegistryResultStatus.SUCCESS,
                    records=[],
                    metadata={"records_found": 0},
                )

            retryable = status_code == 429 or status_code >= 500
            return RegistryProviderResult(
                provider="opencorporates",
                status=(
                    RegistryResultStatus.PARTIAL
                    if retryable
                    else RegistryResultStatus.FAILED
                ),
                error=f"OpenCorporates HTTP {status_code}.",
                metadata={
                    "failure_isolated": True,
                    "retryable": retryable,
                    "rate_limited": status_code == 429,
                },
            )
        except httpx.RequestError as exc:
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.PARTIAL,
                error=str(exc),
                metadata={
                    "failure_isolated": True,
                    "retryable": True,
                },
            )
        except Exception as exc:
            return RegistryProviderResult(
                provider="opencorporates",
                status=RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

    @staticmethod
    def _company_rows(payload) -> list[dict]:
        results = payload.get("results")
        if not isinstance(results, dict):
            raise ValueError(
                "Malformed OpenCorporates response: missing results object."
            )

        companies = results.get("companies", [])
        if not isinstance(companies, list):
            raise ValueError(
                "Malformed OpenCorporates response: companies must be a list."
            )

        rows: list[dict] = []
        for item in companies:
            if not isinstance(item, dict):
                continue
            company = item.get("company")
            if isinstance(company, dict):
                rows.append(company)
        return rows

    def _to_record(
        self,
        company: dict,
        *,
        exact_identifier: bool,
    ) -> RegistryRecord | None:
        name = str(company.get("name") or "").strip()
        company_number = str(
            company.get("company_number") or ""
        ).strip()
        jurisdiction_code = str(
            company.get("jurisdiction_code") or ""
        ).strip().lower()

        if not name or not company_number or not jurisdiction_code:
            return None

        country = self._country_from_jurisdiction(
            jurisdiction_code
        )
        record_id = f"{jurisdiction_code}/{company_number}"

        source = (
            company.get("source")
            if isinstance(company.get("source"), dict)
            else {}
        )

        legal_address = str(
            company.get("registered_address_in_full") or ""
        ).strip() or self._structured_address(
            company.get("registered_address")
        )

        opencorporates_url = str(
            company.get("opencorporates_url") or ""
        ).strip() or (
            "https://opencorporates.com/companies/"
            f"{jurisdiction_code}/{company_number}"
        )

        return RegistryRecord(
            provider="opencorporates",
            domain=RegistryDomain.BUSINESS,
            record_id=record_id,
            display_name=name,
            country=country,
            jurisdiction=jurisdiction_code,
            status=(
                str(company.get("current_status") or "").strip()
                or None
            ),
            registration_id=company_number,
            legal_form=(
                str(company.get("company_type") or "").strip()
                or None
            ),
            legal_address=legal_address,
            source_url=opencorporates_url,
            confidence=0.95 if exact_identifier else 0.76,
            reliability=0.85,
            identifiers={
                "REGISTRATION_ID": company_number,
                "OPENCORPORATES": record_id,
            },
            metadata={
                "aggregator": "OpenCorporates",
                "registry_url": (
                    str(company.get("registry_url") or "").strip()
                    or None
                ),
                "incorporation_date": company.get(
                    "incorporation_date"
                ),
                "dissolution_date": company.get(
                    "dissolution_date"
                ),
                "inactive": company.get("inactive"),
                "branch": company.get("branch"),
                "branch_status": company.get("branch_status"),
                "source_publisher": (
                    str(source.get("publisher") or "").strip()
                    or None
                ),
                "source_url": (
                    str(source.get("url") or "").strip()
                    or None
                ),
                "source_retrieved_at": source.get(
                    "retrieved_at"
                ),
                "opencorporates_updated_at": company.get(
                    "updated_at"
                ),
            },
            entity_kind=RegistryEntityKind.COMPANY,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.85,
            raw_reference=record_id,
        )

    @staticmethod
    def _country_from_jurisdiction(
        jurisdiction_code: str,
    ) -> str | None:
        head = jurisdiction_code.split("_", 1)[0].upper()
        if len(head) == 2 and head.isalpha():
            return head
        return None

    @staticmethod
    def _structured_address(value) -> str | None:
        if not isinstance(value, dict):
            return None

        parts: list[str] = []
        for key in (
            "street_address",
            "locality",
            "region",
            "postal_code",
            "country",
        ):
            item = str(value.get(key) or "").strip()
            if item:
                parts.append(item)

        return ", ".join(parts) or None
