from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.application.registry_persistence_service import RegistryPersistenceService
from app.models.source import SourceType
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySearchResult,
    RegistrySourceType,
)


class _SourceRepository:
    def __init__(self) -> None:
        self.rows = []

    def get_by_case(self, _case_id):
        return list(self.rows)


class _SourceService:
    def __init__(self) -> None:
        self.repository = _SourceRepository()

    def create_source(self, *, case_id, name, source_type, path, description):
        row = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            name=name,
            source_type=source_type,
            original_path=path,
            description=description,
            is_deleted=False,
        )
        self.repository.rows.append(row)
        return row


class _EvidenceRepository:
    def __init__(self) -> None:
        self.rows = []

    def get_by_source(self, source_id):
        return [row for row in self.rows if row.source_id == source_id]


class _EvidenceService:
    def __init__(self) -> None:
        self.repository = _EvidenceRepository()

    def create_evidence(
        self,
        *,
        case_id,
        source_id,
        evidence_type,
        title,
        value,
        description,
        metadata_json,
    ):
        row = SimpleNamespace(
            id=uuid4(),
            case_id=case_id,
            source_id=source_id,
            evidence_type=evidence_type,
            title=title,
            value=value,
            description=description,
            metadata_json=metadata_json,
            is_deleted=False,
        )
        self.repository.rows.append(row)
        return row


class _EntityRepository:
    def get_case_entities_by_type(self, _case_id, _entity_type):
        return []


class _EntityService:
    def __init__(self) -> None:
        self.repository = _EntityRepository()
        self.resolve_calls = 0
        self.update_calls = 0

    def resolve_or_create_entity(self, **_kwargs):
        self.resolve_calls += 1
        raise AssertionError("Court persistence must not auto-create an Entity.")

    def update_metadata(self, *_args, **_kwargs):
        self.update_calls += 1
        raise AssertionError("Court persistence must not mutate Entity identity metadata.")


class _EvidenceLinkService:
    def __init__(self) -> None:
        self.calls = 0

    def ensure_link(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("Court persistence must not auto-link Evidence to an Entity.")


def _court_record(*, safe: bool = True) -> RegistryRecord:
    metadata = {
        "dataset_year": 2026,
        "case_number": "761/1234/26",
        "court_name": "Test Court",
        "legal_outcome": "unknown",
        "legal_outcome_inference_prohibited": safe,
        "person_identity_inference_prohibited": safe,
    }
    return RegistryRecord(
        provider="ua_edrsr",
        domain=RegistryDomain.COURT,
        record_id="decision:123456789",
        display_name="Рішення · справа 761/1234/26",
        country="UA",
        jurisdiction="UA",
        status="active",
        source_url="https://reyestr.court.gov.ua/Review/123456789",
        confidence=0.99,
        reliability=0.96,
        identifiers={
            "EDRSR_DOC_ID": "123456789",
            "CASE_NUMBER": "761/1234/26",
        },
        metadata=metadata,
        entity_kind=RegistryEntityKind.COURT_DECISION,
        source_type=RegistrySourceType.OFFICIAL_OPEN_DATA,
        trust_score=0.96,
        raw_reference="ua-edrsr:123456789",
        sensitive_legal_data=True,
    )


def _search_result(record: RegistryRecord) -> RegistrySearchResult:
    query = RegistryQuery(
        domain=RegistryDomain.COURT,
        kind=RegistryQueryKind.CASE_NUMBER,
        value="761/1234/26",
        country="UA",
        sources=("ua_edrsr",),
        entity_kind=RegistryEntityKind.COURT_CASE,
    )
    provider_result = RegistryProviderResult(
        provider="ua_edrsr",
        status=RegistryResultStatus.SUCCESS,
        records=[record],
    )
    return RegistrySearchResult(
        query=query,
        provider_results=[provider_result],
        records=[record],
    )


def _service():
    source_service = _SourceService()
    evidence_service = _EvidenceService()
    entity_service = _EntityService()
    link_service = _EvidenceLinkService()
    service = RegistryPersistenceService(
        source_service=source_service,
        evidence_service=evidence_service,
        entity_service=entity_service,
        evidence_link_service=link_service,
    )
    return service, source_service, evidence_service, entity_service, link_service


def test_court_decision_persists_evidence_without_identity_resolution() -> None:
    service, source_service, evidence_service, entity_service, link_service = _service()
    result = service.persist(case_id=uuid4(), result=_search_result(_court_record()))

    assert result.errors == []
    assert result.sources_created == 1
    assert result.evidences_created == 1
    assert result.entities_created == 0
    assert result.links_created == 0
    assert len(result.records) == 1
    assert result.records[0].entities == []
    assert result.records[0].resolution_method == "no_identity_resolution"
    assert entity_service.resolve_calls == 0
    assert entity_service.update_calls == 0
    assert link_service.calls == 0

    source = source_service.repository.rows[0]
    assert source.source_type is SourceType.API
    evidence = evidence_service.repository.rows[0]
    payload = json.loads(evidence.metadata_json)
    assert payload["sensitive_legal_data"] is True
    assert payload["legal_safety"] == {
        "legal_outcome": "unknown",
        "legal_outcome_inference_prohibited": True,
        "person_identity_inference_prohibited": True,
        "guilt_or_conviction_inference_prohibited": True,
        "identity_resolution": "not_attempted",
    }
    assert "761/1234/26" in evidence.description
    assert "123456789" in evidence.description


def test_court_snapshot_is_idempotent_even_when_retrieved_at_changes() -> None:
    service, *_ = _service()
    case_id = uuid4()

    first = _court_record()
    first.retrieved_at = "2026-09-13T18:00:00+00:00"
    first_result = service.persist(case_id=case_id, result=_search_result(first))
    assert first_result.evidences_created == 1

    second = _court_record()
    second.retrieved_at = "2026-09-13T18:01:00+00:00"
    second_result = service.persist(case_id=case_id, result=_search_result(second))

    assert second_result.sources_created == 0
    assert second_result.evidences_created == 0
    assert second_result.entities_created == 0
    assert second_result.links_created == 0
    assert second_result.errors == []


def test_court_record_without_inference_guardrails_is_rejected() -> None:
    service, source_service, evidence_service, entity_service, link_service = _service()
    result = service.persist(case_id=uuid4(), result=_search_result(_court_record(safe=False)))

    assert result.records == []
    assert result.skipped_records == 1
    assert result.errors
    assert source_service.repository.rows == []
    assert evidence_service.repository.rows == []
    assert entity_service.resolve_calls == 0
    assert link_service.calls == 0
