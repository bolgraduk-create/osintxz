from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.registry_ua_edrsr_sync_service import UaEdrsrSyncService
from app.infrastructure.registries.ukraine_edrsr_downloader import (
    UaEdrsrDatasetResources,
    UaEdrsrResource,
)
from app.models.registry_ua_edrsr import UaEdrsrDecision, UaEdrsrSyncState
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


class _DatasetClient:
    def __init__(self, resources):
        self.resources = resources

    def resolve_year(self, dataset_year: int):
        assert dataset_year == self.resources.dataset_year
        return self.resources


def _runtime():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UaEdrsrDecision.__table__.create(engine)
    UaEdrsrSyncState.__table__.create(engine)
    session = Session(engine)
    return session, UaEdrsrRepository(session)


def _resources():
    resource = UaEdrsrResource(
        name="edrsr_data_2026.zip",
        resource_id="r1",
        url="https://data.gov.ua/example/edrsr_data_2026.zip",
        modified_at="2026-09-13",
        hash_value="abc",
    )
    return UaEdrsrDatasetResources(2026, "d1", "dataset", "2026-09-13", resource)


def test_yearly_generation_activation_does_not_delete_previous_generation_early():
    session, repository = _runtime()
    old_state = repository.ensure_sync_state(2026)
    old_state.status = "ready"
    old_state.active_generation = "old"
    old_state.metadata_json = '{"official_fingerprint":"old"}'
    repository.bulk_insert([
        {
            "dataset_year": 2026,
            "generation": "old",
            "doc_id": 1,
            "cause_num": "1/1",
            "cause_num_normalized": "1/1",
        }
    ])
    session.commit()

    service = UaEdrsrSyncService(
        repository=repository,
        dataset_client=_DatasetClient(_resources()),
    )
    plan = service.build_plan(dataset_year=2026)
    assert plan.unchanged is False
    service.begin(plan)
    session.flush()

    assert repository.active_generations()[2026] == "old"
    assert session.query(UaEdrsrDecision).filter_by(generation="old").count() == 1

    repository.bulk_insert([
        {
            "dataset_year": 2026,
            "generation": plan.generation,
            "doc_id": 2,
            "cause_num": "2/2",
            "cause_num_normalized": "2/2",
        }
    ])
    service.mark_ready(plan, record_count=1, source_hash="sha256")
    assert repository.active_generations()[2026] == plan.generation
    assert session.query(UaEdrsrDecision).filter_by(generation="old").count() == 1

    assert service.cleanup_old_generations(plan) == 1
    assert session.query(UaEdrsrDecision).filter_by(generation="old").count() == 0


def test_same_official_fingerprint_is_reported_unchanged():
    session, repository = _runtime()
    resources = _resources()
    state = repository.ensure_sync_state(2026)
    state.status = "ready"
    state.active_generation = resources.fingerprint
    state.metadata_json = (
        '{"official_fingerprint":"' + resources.fingerprint + '"}'
    )
    session.commit()

    service = UaEdrsrSyncService(
        repository=repository,
        dataset_client=_DatasetClient(resources),
    )
    assert service.build_plan(dataset_year=2026).unchanged is True


def test_failed_refresh_preserves_previous_active_fingerprint_and_count():
    session, repository = _runtime()
    old_state = repository.ensure_sync_state(2026)
    old_state.status = "ready"
    old_state.active_generation = "old-generation"
    old_state.record_count = 123
    old_state.metadata_json = '{"official_fingerprint":"old-fingerprint"}'
    session.commit()

    service = UaEdrsrSyncService(
        repository=repository,
        dataset_client=_DatasetClient(_resources()),
    )
    plan = service.build_plan(dataset_year=2026)
    service.begin(plan)
    assert repository.active_official_fingerprint(2026) == "old-fingerprint"
    assert repository.get_sync_state(2026).record_count == 123

    service.mark_failed(plan, "broken refresh")
    state = repository.get_sync_state(2026)
    assert state.active_generation == "old-generation"
    assert state.record_count == 123
    assert repository.active_official_fingerprint(2026) == "old-fingerprint"
    assert repository.ready_years() == (2026,)
