from __future__ import annotations

import re

import httpx

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


class PolandKrsRegistryProvider(RegistryProvider):
    """Official Polish KRS Open API provider."""

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="pl_krs",
            display_name="Poland KRS — Krajowy Rejestr Sądowy",
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset(
                {RegistryQueryKind.REGISTRATION_ID}
            ),
            countries=frozenset({"PL"}),
            global_scope=False,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=16,
            access_mode=RegistryAccessMode.PUBLIC_AUTOMATED,
            source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
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
                error="Unsupported Poland KRS query.",
            )

        try:
            krs_number = self._normalize_krs(query.value)
        except ValueError as exc:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
            )

        last_404: httpx.HTTPStatusError | None = None

        for register in ("P", "S"):
            try:
                payload = self.client.get_current_extract(
                    krs_number,
                    register=register,
                    timeout=query.timeout,
                )
                record = self._to_record(
                    payload,
                    expected_krs=krs_number,
                    register=register,
                )
                if record is None:
                    return RegistryProviderResult(
                        provider=self.info.name,
                        status=RegistryResultStatus.FAILED,
                        error="Malformed KRS extract response.",
                        metadata={"failure_isolated": True},
                    )

                return RegistryProviderResult(
                    provider=self.info.name,
                    status=RegistryResultStatus.SUCCESS,
                    records=[record],
                    metadata={
                        "records_found": 1,
                        "official_registry": True,
                        "open_api": True,
                        "register": register,
                        "personal_data_anonymized_by_source": True,
                    },
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 404:
                    last_404 = exc
                    continue

                retryable = status_code == 429 or status_code >= 500
                return RegistryProviderResult(
                    provider=self.info.name,
                    status=(
                        RegistryResultStatus.PARTIAL
                        if retryable
                        else RegistryResultStatus.FAILED
                    ),
                    error=f"Poland KRS HTTP {status_code}.",
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

        if last_404 is not None:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.SUCCESS,
                records=[],
                metadata={
                    "records_found": 0,
                    "registers_checked": ["P", "S"],
                },
            )

        return RegistryProviderResult(
            provider=self.info.name,
            status=RegistryResultStatus.SUCCESS,
            records=[],
            metadata={"records_found": 0},
        )

    @staticmethod
    def _normalize_krs(value: str) -> str:
        compact = re.sub(r"\s+", "", value.strip())
        if not compact.isdigit() or not 1 <= len(compact) <= 10:
            raise ValueError("Malformed KRS registration number.")
        return compact.zfill(10)

    def _to_record(
        self,
        payload: dict,
        *,
        expected_krs: str,
        register: str,
    ) -> RegistryRecord | None:
        odpis = payload.get("odpis")
        if not isinstance(odpis, dict):
            return None

        dane = odpis.get("dane")
        if not isinstance(dane, dict):
            return None

        dzial1 = dane.get("dzial1")
        if not isinstance(dzial1, dict):
            return None

        dane_podmiotu = dzial1.get("danePodmiotu")
        if not isinstance(dane_podmiotu, dict):
            return None

        name = str(dane_podmiotu.get("nazwa") or "").strip()
        identifiers = dane_podmiotu.get("identyfikatory")
        if not isinstance(identifiers, dict):
            identifiers = {}

        returned_krs = str(
            identifiers.get("krs")
            or odpis.get("naglowekP", {}).get("numerKRS")
            or expected_krs
        ).strip()

        returned_krs = self._normalize_krs(returned_krs)
        if returned_krs != expected_krs or not name:
            return None

        nip = str(identifiers.get("nip") or "").strip() or None
        regon = str(identifiers.get("regon") or "").strip() or None

        sied = dzial1.get("siedzibaIAdres")
        address = None
        headquarters = None
        if isinstance(sied, dict):
            address = self._format_address(sied.get("adres"))
            headquarters = self._format_headquarters(
                sied.get("siedziba")
            )

        ids = {"REGISTRATION_ID": returned_krs, "KRS": returned_krs}
        if nip:
            ids["TAX_ID"] = nip
            ids["NIP"] = nip
        if regon:
            ids["REGON"] = regon

        legal_form = (
            str(dane_podmiotu.get("formaPrawna") or "").strip()
            or None
        )

        return RegistryRecord(
            provider=self.info.name,
            domain=RegistryDomain.BUSINESS,
            record_id=returned_krs,
            display_name=name,
            country="PL",
            jurisdiction=f"PL-KRS-{register}",
            status="registered",
            registration_id=returned_krs,
            legal_form=legal_form,
            legal_address=address,
            headquarters_address=headquarters,
            source_url=(
                "https://api-krs.ms.gov.pl/api/krs/"
                f"OdpisAktualny/{returned_krs}"
                f"?rejestr={register}&format=json"
            ),
            confidence=0.99,
            reliability=0.98,
            identifiers=ids,
            metadata={
                "official_registry": "Krajowy Rejestr Sądowy",
                "register": register,
                "short_name": (
                    str(dane_podmiotu.get("nazwaSkrocona") or "").strip()
                    or None
                ),
                "registration_date": dzial1.get("dataRejestracji"),
                "open_api_personal_data_anonymized": True,
            },
            entity_kind=RegistryEntityKind.COMPANY,
            source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
            trust_score=0.98,
            raw_reference=returned_krs,
        )

    @staticmethod
    def _format_address(value) -> str | None:
        if not isinstance(value, dict):
            return None
        parts: list[str] = []
        for key in (
            "ulica",
            "nrDomu",
            "nrLokalu",
            "miejscowosc",
            "kodPocztowy",
            "poczta",
            "kraj",
        ):
            item = str(value.get(key) or "").strip()
            if item:
                parts.append(item)
        return ", ".join(parts) or None

    @staticmethod
    def _format_headquarters(value) -> str | None:
        if not isinstance(value, dict):
            return None
        parts: list[str] = []
        for key in ("miejscowosc", "gmina", "powiat", "wojewodztwo"):
            item = str(value.get(key) or "").strip()
            if item:
                parts.append(item)
        return ", ".join(parts) or None
