from dataclasses import replace
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.application.registry_persistence_service import RegistryPersistenceService
from app.models.case import Case
from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence
from app.models.evidence_entity import EvidenceEntity
from app.models.source import Source
from app.registry_intelligence.contracts import (
    RegistryDomain, RegistryQuery, RegistryQueryKind, RegistryRecord,
    RegistryProviderResult, RegistryResultStatus, RegistrySearchResult,
)
from app.services.entity_service import EntityService
from app.services.evidence_service import EvidenceService
from app.services.evidence_link_service import EvidenceLinkService
from app.services.source_service import SourceService


@pytest.fixture
def runtime():
    engine = create_engine("sqlite:///:memory:")
    for model in (Case, Source, Evidence, Entity, EvidenceEntity):
        model.__table__.create(engine)
    with Session(engine) as session:
        case = Case(title="Registry integration fixture")
        session.add(case)
        session.flush()
        service = RegistryPersistenceService(
            source_service=SourceService(session), evidence_service=EvidenceService(session),
            entity_service=EntityService(session), evidence_link_service=EvidenceLinkService(session),
        )
        yield session, case.id, service
    engine.dispose()


def record(**kwargs):
    return replace(RegistryRecord(
        provider="gleif", domain=RegistryDomain.BUSINESS, record_id="506700GE1G29325QX363",
        display_name="Example Foundation", lei="506700GE1G29325QX363", country="CH",
        legal_address="Basel, CH", source_url="https://api.gleif.org/api/v1/lei-records/506700GE1G29325QX363",
        registration_id="CHE-200.595.965", confidence=0.96, reliability=0.97,
    ), **kwargs)


def search(*records):
    return RegistrySearchResult(
        query=RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.NAME, "Example"),
        records=list(records), provider_results=[RegistryProviderResult(
            provider=r.provider, status=RegistryResultStatus.SUCCESS, records=[r]) for r in records],
    )


def test_record_to_real_case_source_evidence_entities_and_idempotent_links(runtime):
    session, case_id, service = runtime
    first = service.persist(case_id=case_id, result=search(record()))
    second = service.persist(case_id=case_id, result=search(record()))
    assert (first.sources_created, first.evidences_created, first.entities_created, first.links_created) == (1, 1, 2, 2)
    assert (second.sources_created, second.evidences_created, second.entities_created, second.links_created) == (0, 0, 0, 0)
    assert len(session.scalars(select(Entity)).all()) == 2
    assert {e.entity_type for e in first.records[0].entities} == {EntityType.ORGANIZATION, EntityType.ADDRESS}
    metadata = json.loads(first.records[0].evidence.metadata_json)
    assert metadata["record"]["lei"] == record().lei
    assert metadata["record"]["registration_id"] == record().registration_id
    assert metadata["retrieved_at"] and metadata["provider"] == "gleif"
    assert metadata["ownership_inferred"] is False
    assert session.in_transaction()  # Adapter did not commit the caller's work.


def test_independent_providers_same_lei_fuse_and_preserve_each_source(runtime):
    session, case_id, service = runtime
    result = service.persist(case_id=case_id, result=search(record(), record(provider="official_second", record_id="other")))
    assert result.sources_created == 2 and result.evidences_created == 2
    assert result.entities_created == 2
    assert result.records[0].entities[0].id == result.records[1].entities[0].id
    assert result.records[1].resolution_method == "exact_lei"
    assert len(session.scalars(select(EvidenceEntity)).all()) == 4


def test_same_name_different_lei_does_not_fuse(runtime):
    session, case_id, service = runtime
    result = service.persist(case_id=case_id, result=search(record(), record(
        record_id="different", lei="5493001KJTIIGC8Y1R12")))
    assert result.records[0].entities[0].id != result.records[1].entities[0].id


def test_unscoped_registration_number_does_not_merge_providers(runtime):
    _, case_id, service = runtime
    result = service.persist(case_id=case_id, result=search(
        record(lei=None), record(lei=None, provider="other_registry")))
    assert result.records[0].entities[0].id != result.records[1].entities[0].id


def test_changed_record_keeps_old_evidence_and_same_organization(runtime):
    _, case_id, service = runtime
    first = service.persist(case_id=case_id, result=search(record()))
    changed = service.persist(case_id=case_id, result=search(record(display_name="Renamed Foundation")))
    assert changed.evidences_created == 1 and changed.entities_created == 0
    assert first.records[0].entities[0].id == changed.records[0].entities[0].id
    assert first.records[0].evidence.id != changed.records[0].evidence.id


def test_court_record_does_not_infer_person_or_organization(runtime):
    _, case_id, service = runtime
    result = service.persist(case_id=case_id, result=search(record(domain=RegistryDomain.COURT)))
    assert result.evidences_created == 1 and result.entities_created == 0


def test_candidate_or_failed_provider_is_not_persisted(runtime):
    _, case_id, service = runtime
    candidate = service.persist(case_id=case_id, result=search(record(metadata={"candidate_only": True})))
    assert candidate.skipped_records == 1 and candidate.sources_created == 0
    failed = search(record())
    failed.provider_results[0].status = RegistryResultStatus.FAILED
    assert service.persist(case_id=case_id, result=failed).sources_created == 0


def test_registry_changed_sources_compile():
    for relative in ["app/application/registry_persistence_service.py", "app/application/registry_intelligence_service.py", "app/core/service_container.py", "app/registry_intelligence/query_detection.py", "app/registry_intelligence/providers/gleif.py", "app/infrastructure/registries/gleif_client.py", "app/interface/desktop/workers/investigation_search_worker.py", "app/interface/desktop/views/workspace/investigation_search_view.py"]:
        path = Path(relative)
        compile(path.read_bytes(), str(path), "exec")


def test_registry_is_searchable_through_existing_indexing_service(runtime):
    from types import SimpleNamespace
    from app.models.search_index import SearchIndex
    from app.repositories.search_index_repository import SearchIndexRepository
    from app.services.search_index_builder import SearchIndexBuilder
    from app.services.search_indexing_service import SearchIndexingService

    session, case_id, service = runtime
    SearchIndex.__table__.create(session.bind)
    indexer = SearchIndexingService(
        search_index_builder=SearchIndexBuilder(session),
        search_index_repository=SearchIndexRepository(session),
        search_embedding_repository=SimpleNamespace(delete_for_search_index=lambda **kwargs: None),
        search_embedding_indexer=None,
    )
    service.search_indexing_service = indexer
    service.evidence_service.search_indexing_service = indexer
    service.persist(case_id=case_id, result=search(record()))
    service.persist(case_id=case_id, result=search(record()))
    indexes = session.scalars(select(SearchIndex)).all()
    assert len(indexes) == 3
    assert any(record().lei in i.content for i in indexes)
    assert any(record().registration_id in i.content for i in indexes)
    assert any(record().display_name in i.content for i in indexes)


def test_registry_caller_rollback_removes_partial_work(runtime):
    session, case_id, service = runtime
    session.commit()
    service.persist(case_id=case_id, result=search(record()))
    session.rollback()
    assert session.scalars(select(Entity)).all() == []
    assert session.scalars(select(Evidence)).all() == []
    assert session.scalars(select(Source)).all() == []


def test_registry_case_boundaries_do_not_fuse(runtime):
    session, case_id, service = runtime
    other_case = Case(title="Other case")
    session.add(other_case)
    session.flush()
    first = service.persist(case_id=case_id, result=search(record()))
    second = service.persist(case_id=other_case.id, result=search(record()))
    assert first.records[0].entities[0].id != second.records[0].entities[0].id
