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


class CourtListenerRegistryProvider(RegistryProvider):
    """
    US case-law search through CourtListener's Legal Search API v4.

    R10 intentionally covers case-law opinion clusters only (type=o). PACER /
    RECAP search is a separate R11 concern and is not mixed into this provider.
    """

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(
            name="courtlistener",
            display_name="CourtListener US Case Law",
            domains=frozenset({RegistryDomain.COURT, RegistryDomain.LEGAL}),
            query_kinds=frozenset(
                {RegistryQueryKind.CASE_NUMBER, RegistryQueryKind.NAME}
            ),
            countries=frozenset({"US"}),
            global_scope=False,
            public_data_only=True,
            requires_credentials=not self.client.configured,
            default_enabled=True,
            priority=35,
            access_mode=RegistryAccessMode.API,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.90,
            sensitive_legal_data=True,
        )

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported CourtListener query.",
            )
        if not self.client.configured:
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="CourtListener API token is not configured.",
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )

        field = (
            "docketNumber"
            if query.kind is RegistryQueryKind.CASE_NUMBER
            else "caseName"
        )

        try:
            payload = self.client.search_case_law(
                query.value,
                field=field,
                limit=query.limit,
                timeout=query.timeout,
            )
            rows = payload.get("results", [])
            if not isinstance(rows, list):
                raise ValueError(
                    "Malformed CourtListener response: results must be a list."
                )

            records = [
                record
                for row in rows
                if isinstance(row, dict)
                if (record := self._to_record(row)) is not None
            ]

            if query.kind is RegistryQueryKind.CASE_NUMBER:
                requested = self._normalize_docket(query.value)
                records = [
                    record
                    for record in records
                    if self._normalize_docket(
                        str(record.metadata.get("docket_number") or "")
                    )
                    == requested
                ]

            records = records[: query.limit]
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "upstream_count": payload.get("count"),
                    "credentials_required": True,
                    "credentials_configured": True,
                    "case_law_only": True,
                    "pacer_recap_included": False,
                    "identity_warning": (
                        "A case-law hit or name mention is not proof of "
                        "identity, guilt, liability, or conviction."
                    ),
                },
            )

        except CourtListenerCredentialsError as exc:
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=str(exc),
                metadata={
                    "credentials_required": True,
                    "credentials_configured": False,
                },
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in {401, 403}:
                return RegistryProviderResult(
                    provider="courtlistener",
                    status=RegistryResultStatus.FAILED,
                    error=f"CourtListener credentials rejected (HTTP {code}).",
                    metadata={
                        "failure_isolated": True,
                        "credentials_invalid": True,
                        "retryable": False,
                    },
                )
            if code == 404:
                return RegistryProviderResult(
                    provider="courtlistener",
                    status=RegistryResultStatus.SUCCESS,
                    records=[],
                    metadata={"records_found": 0},
                )
            retryable = code == 429 or code >= 500
            return RegistryProviderResult(
                provider="courtlistener",
                status=(
                    RegistryResultStatus.PARTIAL
                    if retryable
                    else RegistryResultStatus.FAILED
                ),
                error=f"CourtListener HTTP {code}.",
                metadata={
                    "failure_isolated": True,
                    "retryable": retryable,
                    "rate_limited": code == 429,
                },
            )
        except httpx.RequestError as exc:
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.PARTIAL,
                error=str(exc),
                metadata={
                    "failure_isolated": True,
                    "retryable": True,
                },
            )
        except Exception as exc:
            return RegistryProviderResult(
                provider="courtlistener",
                status=RegistryResultStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

    def _to_record(self, row: dict) -> RegistryRecord | None:
        cluster_id = str(row.get("cluster_id") or "").strip()
        case_name = str(
            row.get("caseNameFull") or row.get("caseName") or ""
        ).strip()
        if not cluster_id or not case_name:
            return None

        absolute_url = str(row.get("absolute_url") or "").strip()
        source_url = (
            f"https://www.courtlistener.com{absolute_url}"
            if absolute_url.startswith("/")
            else absolute_url or None
        )
        docket_number = str(row.get("docketNumber") or "").strip() or None
        citations = row.get("citation")
        if not isinstance(citations, list):
            citations = []

        identifiers = {"COURTLISTENER_CLUSTER_ID": cluster_id}
        if docket_number:
            identifiers["CASE_NUMBER"] = docket_number

        return RegistryRecord(
            provider="courtlistener",
            domain=RegistryDomain.COURT,
            record_id=f"opinion-cluster:{cluster_id}",
            display_name=case_name,
            country="US",
            jurisdiction=(
                str(row.get("court_id") or "").strip() or None
            ),
            status=str(row.get("status") or "").strip() or None,
            registration_id=None,
            source_url=source_url,
            confidence=0.98 if docket_number else 0.78,
            reliability=0.90,
            identifiers=identifiers,
            metadata={
                "docket_number": docket_number,
                "docket_id": row.get("docket_id"),
                "court": row.get("court"),
                "court_id": row.get("court_id"),
                "date_filed": row.get("dateFiled"),
                "date_argued": row.get("dateArgued"),
                "citations": [str(x) for x in citations],
                "cite_count": row.get("citeCount"),
                "case_name_full": row.get("caseNameFull"),
                "opinion_cluster_id": cluster_id,
                "legal_outcome_inferred": False,
                "identity_confirmed": False,
                "pacer_recap": False,
            },
            entity_kind=RegistryEntityKind.COURT_DECISION,
            source_type=RegistrySourceType.AGGREGATOR,
            trust_score=0.90,
            raw_reference=cluster_id,
            sensitive_legal_data=True,
        )

    @staticmethod
    def _normalize_docket(value: str) -> str:
        # CourtListener data can contain cosmetic prefixes/spaces/dash variants.
        text = value.strip().casefold()
        text = re.sub(r"^no\.\s*", "", text)
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"\s+", "", text)
        return text.rstrip(".")
