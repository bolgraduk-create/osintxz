from __future__ import annotations

import re

import httpx

from app.infrastructure.registries.courtlistener_client import (
    CourtListenerCredentialsError,
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


class CourtListenerRecapRegistryProvider(RegistryProvider):
    """Search federal PACER dockets already present in CourtListener/RECAP."""

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="courtlistener_recap",
            display_name="CourtListener RECAP Federal Dockets",
            domains=frozenset({RegistryDomain.COURT, RegistryDomain.LEGAL}),
            query_kinds=frozenset({RegistryQueryKind.CASE_NUMBER, RegistryQueryKind.NAME}),
            countries=frozenset({"US"}),
            global_scope=False,
            public_data_only=True,
            requires_credentials=not self.client.configured,
            default_enabled=True,
            priority=36,
            access_mode=RegistryAccessMode.API,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.92,
            sensitive_legal_data=True,
        )

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported CourtListener RECAP query.",
            )
        if not self.client.configured:
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="CourtListener API token is not configured.",
                metadata={"credentials_required": True, "credentials_configured": False},
            )

        field = "docketNumber" if query.kind is RegistryQueryKind.CASE_NUMBER else "caseName"
        try:
            payload = self.client.search_recap_dockets(
                query.value, field=field, limit=query.limit, timeout=query.timeout
            )
            rows = payload.get("results", [])
            if not isinstance(rows, list):
                raise ValueError("Malformed CourtListener RECAP response: results must be a list.")
            records = [
                rec
                for row in rows
                if isinstance(row, dict)
                if (rec := self._to_record(row)) is not None
            ]
            if query.kind is RegistryQueryKind.CASE_NUMBER:
                wanted = self._normalize_docket(query.value)
                records = [
                    rec for rec in records
                    if self._normalize_docket(str(rec.metadata.get("docket_number") or "")) == wanted
                ]
            records = records[: query.limit]
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "upstream_count": payload.get("count"),
                    "credentials_required": True,
                    "credentials_configured": True,
                    "recap_archive_only": True,
                    "paid_pacer_fetch_performed": False,
                    "identity_warning": "A federal docket hit or case-name match is not proof of identity, guilt, liability, or conviction.",
                },
            )
        except CourtListenerCredentialsError as exc:
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
                metadata={"credentials_required": True, "credentials_configured": False},
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in {401, 403}:
                return RegistryProviderResult(
                    provider="courtlistener_recap",
                    status=RegistryResultStatus.FAILED,
                    error=f"CourtListener credentials rejected (HTTP {code}).",
                    metadata={"failure_isolated": True, "credentials_invalid": True, "retryable": False},
                )
            if code == 404:
                return RegistryProviderResult(
                    provider="courtlistener_recap",
                    status=RegistryResultStatus.SUCCESS,
                    records=[], metadata={"records_found": 0},
                )
            retryable = code == 429 or code >= 500
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.PARTIAL if retryable else RegistryResultStatus.FAILED,
                error=f"CourtListener RECAP HTTP {code}.",
                metadata={"failure_isolated": True, "retryable": retryable, "rate_limited": code == 429},
            )
        except httpx.RequestError as exc:
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.PARTIAL,
                error=str(exc),
                metadata={"failure_isolated": True, "retryable": True},
            )
        except Exception as exc:
            return RegistryProviderResult(
                provider="courtlistener_recap",
                status=RegistryResultStatus.FAILED,
                error=str(exc), metadata={"failure_isolated": True},
            )

    def _to_record(self, row: dict) -> RegistryRecord | None:
        docket_id = str(row.get("docket_id") or row.get("id") or "").strip()
        case_name = str(row.get("caseNameFull") or row.get("caseName") or "").strip()
        if not docket_id or not case_name:
            return None
        docket_number = str(row.get("docketNumber") or "").strip() or None
        absolute_url = str(row.get("absolute_url") or "").strip()
        source_url = (
            f"https://www.courtlistener.com{absolute_url}"
            if absolute_url.startswith("/") else absolute_url or None
        ) or f"https://www.courtlistener.com/docket/{docket_id}/"
        identifiers = {"COURTLISTENER_DOCKET_ID": docket_id}
        if docket_number:
            identifiers["CASE_NUMBER"] = docket_number
        return RegistryRecord(
            provider="courtlistener_recap",
            domain=RegistryDomain.COURT,
            record_id=f"recap-docket:{docket_id}",
            display_name=case_name,
            country="US",
            jurisdiction=str(row.get("court_id") or "").strip() or None,
            status=str(row.get("status") or "").strip() or None,
            source_url=source_url,
            confidence=0.98 if docket_number else 0.76,
            reliability=0.92,
            identifiers=identifiers,
            metadata={
                "docket_number": docket_number,
                "docket_id": docket_id,
                "court": row.get("court"),
                "court_id": row.get("court_id"),
                "date_filed": row.get("dateFiled"),
                "date_terminated": row.get("dateTerminated"),
                "assigned_to": row.get("assignedTo"),
                "referred_to": row.get("referredTo"),
                "cause": row.get("cause"),
                "suit_nature": row.get("suitNature"),
                "jurisdiction_type": row.get("jurisdictionType"),
                "jury_demand": row.get("juryDemand"),
                "pacer_recap": True,
                "recap_archive_only": True,
                "paid_pacer_fetch_performed": False,
                "legal_outcome_inferred": False,
                "identity_confirmed": False,
            },
            entity_kind=RegistryEntityKind.COURT_CASE,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.92,
            raw_reference=docket_id,
            sensitive_legal_data=True,
        )

    @staticmethod
    def _normalize_docket(value: str) -> str:
        text = value.strip().casefold()
        text = re.sub(r"^(case\s+)?no\.\s*", "", text)
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"\s+", "", text)
        return text.rstrip(".")
