from __future__ import annotations

import re

import httpx

from app.infrastructure.registries.vies_client import ViesServiceError
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


class ViesRegistryProvider(RegistryProvider):
    """Exact EU VAT-number validation through the European Commission VIES API."""

    _WIRE_COUNTRIES = frozenset({
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "EL", "ES", "FI", "FR",
        "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
        "SE", "SI", "SK", "XI",
    })
    _QUERY_COUNTRIES = _WIRE_COUNTRIES | frozenset({"GR"})
    _TRANSIENT_SERVICE_ERRORS = frozenset({
        "SERVICE_UNAVAILABLE",
        "MS_UNAVAILABLE",
        "TIMEOUT",
        "SERVER_BUSY",
        "GLOBAL_MAX_CONCURRENT_REQ",
        "MS_MAX_CONCURRENT_REQ",
    })

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="vies",
            display_name="EU VIES VAT Validation",
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset({RegistryQueryKind.VAT_ID}),
            countries=self._QUERY_COUNTRIES,
            global_scope=False,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=8,
            access_mode=RegistryAccessMode.API,
            source_type=RegistrySourceType.OFFICIAL_API,
            trust_score=0.99,
        )

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported VIES query.",
            )

        try:
            wire_country, canonical_country, vat_number = self._parse_query(query)
        except ValueError as exc:
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
            )

        normalized_vat_id = f"{wire_country}{vat_number}"

        try:
            payload = self.client.check_vat(wire_country, vat_number, timeout=query.timeout)
        except ViesServiceError as exc:
            retryable = bool(set(exc.codes) & self._TRANSIENT_SERVICE_ERRORS)
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.PARTIAL if retryable else RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={
                    "failure_isolated": True,
                    "retryable": retryable,
                    "vies_error_codes": list(exc.codes),
                    "checked_vat_id": normalized_vat_id,
                },
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code == 429 or status_code >= 500
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.PARTIAL if retryable else RegistryResultStatus.FAILED,
                error=f"Public registry HTTP {status_code}.",
                metadata={
                    "failure_isolated": True,
                    "retryable": retryable,
                    "checked_vat_id": normalized_vat_id,
                },
            )
        except Exception as exc:
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={
                    "failure_isolated": True,
                    "checked_vat_id": normalized_vat_id,
                },
            )

        valid = payload.get("valid")
        if not isinstance(valid, bool):
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.FAILED,
                error="Malformed VIES response: missing boolean valid field.",
                metadata={
                    "failure_isolated": True,
                    "checked_vat_id": normalized_vat_id,
                },
            )

        response_wire_country = str(payload.get("countryCode") or wire_country).strip().upper()
        response_country = self._canonical_country(response_wire_country)
        response_number = self._compact(str(payload.get("vatNumber") or vat_number))
        response_vat_id = f"{response_wire_country}{response_number}"

        base_metadata = {
            "records_found": 0,
            "public_data_only": True,
            "credentials_required": False,
            "exact_validation": True,
            "valid": valid,
            "checked_vat_id": response_vat_id,
            "request_date": payload.get("requestDate"),
            "request_identifier": str(payload.get("requestIdentifier") or "").strip() or None,
        }

        # valid=false is a completed VIES lookup, not a transport/provider failure.
        if not valid:
            return RegistryProviderResult(
                provider="vies",
                status=RegistryResultStatus.SUCCESS,
                records=[],
                metadata=base_metadata,
            )

        name = self._clean_disclosed_text(payload.get("name"))
        address = self._clean_disclosed_text(payload.get("address"))
        record = RegistryRecord(
            provider="vies",
            domain=RegistryDomain.BUSINESS,
            record_id=response_vat_id,
            display_name=name or response_vat_id,
            country=response_country,
            status="valid",
            legal_address=address,
            source_url="https://ec.europa.eu/taxation_customs/vies/",
            confidence=0.99,
            reliability=0.99,
            identifiers={"VAT_ID": response_vat_id},
            metadata={
                "vies_valid": True,
                "request_date": payload.get("requestDate"),
                "request_identifier": str(payload.get("requestIdentifier") or "").strip() or None,
                "name_disclosed": name is not None,
                "address_disclosed": address is not None,
            },
            entity_kind=RegistryEntityKind.LEGAL_ENTITY,
            source_type=RegistrySourceType.OFFICIAL_API,
            trust_score=0.99,
            raw_reference=response_vat_id,
        )

        base_metadata["records_found"] = 1
        return RegistryProviderResult(
            provider="vies",
            status=RegistryResultStatus.SUCCESS,
            records=[record],
            metadata=base_metadata,
        )

    def _parse_query(self, query: RegistryQuery) -> tuple[str, str, str]:
        compact = self._compact(query.value)
        if len(compact) < 3:
            raise ValueError("Malformed VAT identifier.")

        prefix = compact[:2]
        has_prefix = prefix in self._WIRE_COUNTRIES

        if has_prefix:
            wire_country = prefix
            vat_number = compact[2:]
            canonical_country = self._canonical_country(wire_country)
            if query.country is not None:
                requested_country = self._canonical_country(self._wire_country(query.country))
                if requested_country != canonical_country:
                    raise ValueError("VAT prefix conflicts with RegistryQuery country.")
        else:
            if query.country is None:
                raise ValueError("VIES requires RegistryQuery country or a VAT country prefix.")
            wire_country = self._wire_country(query.country)
            canonical_country = self._canonical_country(wire_country)
            vat_number = compact

        if not 2 <= len(vat_number) <= 14 or not vat_number.isalnum():
            raise ValueError("Malformed VAT identifier.")

        return wire_country, canonical_country, vat_number

    @classmethod
    def _wire_country(cls, country: str) -> str:
        country = country.strip().upper()
        if country == "GR":
            return "EL"
        if country not in cls._WIRE_COUNTRIES:
            raise ValueError(f"Country {country!r} is not supported by VIES.")
        return country

    @staticmethod
    def _canonical_country(country: str) -> str:
        country = country.strip().upper()
        return "GR" if country == "EL" else country

    @staticmethod
    def _compact(value: str) -> str:
        compact = re.sub(r"[\s.\-_/]+", "", value.strip().upper())
        if not compact or not compact.isalnum():
            raise ValueError("VAT identifier contains unsupported characters.")
        return compact

    @staticmethod
    def _clean_disclosed_text(value) -> str | None:
        text = str(value or "").strip()
        if not text or text in {"---", "-", "N/A"}:
            return None
        return text
