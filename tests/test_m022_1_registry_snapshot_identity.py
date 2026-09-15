from __future__ import annotations

from app.application.registry_persistence_service import (
    _digest,
    _registry_snapshot_payload,
)
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryRecord,
    RegistrySourceType,
)


def _record(*, retrieved_at: str, status: str = "ACTIVE") -> RegistryRecord:
    return RegistryRecord(
        provider="gleif",
        domain=RegistryDomain.BUSINESS,
        record_id="506700GE1G29325QX363",
        display_name="GLOBAL LEGAL ENTITY IDENTIFIER FOUNDATION",
        entity_kind=RegistryEntityKind.COMPANY,
        source_type=RegistrySourceType.OFFICIAL_API,
        trust_score=0.97,
        retrieved_at=retrieved_at,
        raw_reference="506700GE1G29325QX363",
        country="CH",
        status=status,
        lei="506700GE1G29325QX363",
        source_url=(
            "https://api.gleif.org/api/v1/lei-records/"
            "506700GE1G29325QX363"
        ),
        confidence=0.96,
        reliability=0.97,
    )


def test_registry_snapshot_identity_ignores_retrieval_time() -> None:
    first = _record(retrieved_at="2026-09-13T10:00:00+00:00")
    second = _record(retrieved_at="2026-09-13T11:00:00+00:00")

    assert _digest(_registry_snapshot_payload(first)) == _digest(
        _registry_snapshot_payload(second)
    )


def test_registry_snapshot_identity_changes_for_real_record_change() -> None:
    first = _record(
        retrieved_at="2026-09-13T10:00:00+00:00",
        status="ACTIVE",
    )
    second = _record(
        retrieved_at="2026-09-13T11:00:00+00:00",
        status="INACTIVE",
    )

    assert _digest(_registry_snapshot_payload(first)) != _digest(
        _registry_snapshot_payload(second)
    )
