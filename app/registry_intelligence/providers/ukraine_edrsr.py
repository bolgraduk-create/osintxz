"""Ukraine EDRSR provider backed by centrally synchronized official open data."""
from __future__ import annotations

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
)
from app.registry_intelligence.countries.ukraine import UA_EDRSR_PROVIDER_INFO
from app.registry_intelligence.provider import RegistryProvider
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


OFFICIAL_EDRSR_DATASET_PAGE = (
    "https://data.gov.ua/dataset/16ab7f06-7414-405f-8354-0a492475272d"
)


class UkraineEdrsrRegistryProvider(RegistryProvider):
    def __init__(self, *, repository: UaEdrsrRepository) -> None:
        self.repository = repository
        self._info = UA_EDRSR_PROVIDER_INFO

    @property
    def info(self):
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported Ukraine EDRSR query.",
            )

        ready_years = self.repository.ready_years()
        if not ready_years:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=(
                    "Registry Backend EDRSR mirror is not synchronized. "
                    "Run the server-side EDRSR ingestion worker before serving queries."
                ),
                metadata={"cache_state": "missing", "action_required": "backend_sync"},
            )

        if query.kind is not RegistryQueryKind.CASE_NUMBER:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=(
                    "Initial EDRSR provider supports exact case-number queries only. "
                    "Person-name matching is intentionally disabled for legal-safety reasons."
                ),
            )

        rows = self.repository.search_case_number(query.value, limit=query.limit)
        records = [self._to_record(row) for row in rows]
        return RegistryProviderResult(
            provider=self.info.name,
            status=RegistryResultStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "country": "UA",
                "ready_years": list(ready_years),
                "public_data_only": True,
                "query_semantics": "exact_case_number",
                "identity_warning": (
                    "A court-case or court-decision match does not identify a person "
                    "and must not be interpreted as guilt or conviction."
                ),
            },
        )

    def _to_record(self, row) -> RegistryRecord:
        active = row.status == 1
        decision_label = row.judgment_name or "Судове рішення"
        case_label = row.cause_num or f"EDRSR {row.doc_id}"
        metadata = {
            "dataset_year": row.dataset_year,
            "court_code": row.court_code,
            "court_name": row.court_name,
            "court_instance": row.instance_name,
            "court_region": row.region_name,
            "judgment_code": row.judgment_code,
            "judgment_name": row.judgment_name,
            "justice_kind": row.justice_kind,
            "justice_kind_name": row.justice_kind_name,
            "category_code": row.category_code,
            "category_name": row.category_name,
            "case_number": row.cause_num,
            "adjudication_date": row.adjudication_date.isoformat() if row.adjudication_date else None,
            "receipt_date": row.receipt_date.isoformat() if row.receipt_date else None,
            "publication_action_date": row.date_publ.isoformat() if row.date_publ else None,
            "judge": row.judge,
            "registry_status_code": row.status,
            "legal_outcome": "unknown",
            "legal_outcome_inference_prohibited": True,
            "person_identity_inference_prohibited": True,
        }
        return RegistryRecord(
            provider=self.info.name,
            domain=RegistryDomain.COURT,
            record_id=f"decision:{row.doc_id}",
            display_name=f"{decision_label} · справа {case_label}",
            country="UA",
            jurisdiction="UA",
            status="active" if active else "inactive",
            source_url=row.doc_url or OFFICIAL_EDRSR_DATASET_PAGE,
            confidence=0.99,
            reliability=0.96,
            identifiers={
                "EDRSR_DOC_ID": str(row.doc_id),
                **({"CASE_NUMBER": row.cause_num} if row.cause_num else {}),
            },
            metadata=metadata,
            entity_kind=RegistryEntityKind.COURT_DECISION,
            source_type=self.info.source_type,
            trust_score=self.info.trust_score,
            raw_reference=row.raw_reference or f"ua-edrsr:{row.doc_id}",
            sensitive_legal_data=True,
        )
