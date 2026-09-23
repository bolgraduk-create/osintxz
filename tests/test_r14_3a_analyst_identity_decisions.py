from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.person_identity_review_service import (
    IdentityReviewDecision,
    PersonIdentityReviewService,
)
from app.models.entity import EntityType


class FakeSession:
    def flush(self):
        return None


class FakeSourceService:
    def __init__(self):
        self.rows = []

    def create_source(self, **kwargs):
        row = SimpleNamespace(
            id=uuid4(),
            **kwargs,
        )
        self.rows.append(row)
        return row


class FakeEvidenceService:
    def __init__(self):
        self.rows = []
        self.repository = SimpleNamespace(
            session=FakeSession()
        )

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(
            id=uuid4(),
            source_id=kwargs.get("source_id"),
            created_at=datetime.now(UTC)
            + timedelta(microseconds=len(self.rows)),
            metadata_json=kwargs.pop(
                "metadata_json",
                None,
            ),
            **kwargs,
        )
        self.rows.append(row)
        return row


class FakeLinkService:
    def __init__(self, evidence_service):
        self.evidence_service = evidence_service
        self.links = []

    def ensure_link(
        self,
        *,
        evidence_id,
        entity_id,
    ):
        key = (evidence_id, entity_id)
        created = key not in self.links
        if created:
            self.links.append(key)
        return (
            SimpleNamespace(
                evidence_id=evidence_id,
                entity_id=entity_id,
            ),
            created,
        )

    def get_evidence_objects_for_entity(
        self,
        entity_id,
    ):
        evidence_ids = {
            evidence_id
            for evidence_id, linked_id in self.links
            if linked_id == entity_id
        }
        return [
            row
            for row in self.evidence_service.rows
            if row.id in evidence_ids
        ]


def _fixture():
    source = FakeSourceService()
    evidence = FakeEvidenceService()
    links = FakeLinkService(evidence)
    service = PersonIdentityReviewService(
        source_service=source,
        evidence_service=evidence,
        evidence_link_service=links,
    )
    case_id = uuid4()
    person = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Target Person",
    )
    candidate = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.ACCOUNT,
        value="@target",
        confidence=0.73,
        metadata_json='{"connector":"Sherlock","finding_url":"https://example.test/target"}',
    )
    return service, source, evidence, links, person, candidate


def test_confirmed_decision_is_separate_from_machine_confidence():
    service, _source, evidence, links, person, candidate = _fixture()

    result = service.record(
        person=person,
        candidate=candidate,
        decision=IdentityReviewDecision.CONFIRMED,
        note="Known account.",
    )

    assert result.decision == "confirmed"
    assert result.previous_decision == "unreviewed"
    assert result.duplicate is False
    assert len(evidence.rows) == 1

    row = evidence.rows[0]
    assert '"decision": "confirmed"' in row.metadata_json
    assert '"identity_verified": true' in row.metadata_json
    assert '"machine_confidence": 0.73' in row.metadata_json
    assert (row.id, person.id) in links.links
    assert (row.id, candidate.id) in links.links


def test_review_history_is_append_only_and_latest_wins():
    service, _source, evidence, _links, person, candidate = _fixture()

    service.record(
        person=person,
        candidate=candidate,
        decision="review",
        note="Needs another signal.",
    )
    service.record(
        person=person,
        candidate=candidate,
        decision="rejected",
        note="Different person.",
    )

    assert len(evidence.rows) == 2

    latest = service.latest_decisions(
        person.id
    )[str(candidate.id)]

    assert latest["decision"] == "rejected"
    assert latest["label"] == "Rejected"
    assert latest["note"] == "Different person."
    assert latest["historyCount"] == 2


def test_repeating_identical_decision_is_idempotent():
    service, _source, evidence, _links, person, candidate = _fixture()

    first = service.record(
        person=person,
        candidate=candidate,
        decision="review",
        note="Check travel history.",
    )
    second = service.record(
        person=person,
        candidate=candidate,
        decision="review",
        note="Check travel history.",
    )

    assert first.duplicate is False
    assert second.duplicate is True
    assert len(evidence.rows) == 1


def test_unreviewed_is_derived_and_not_persisted():
    service, _source, _evidence, _links, person, candidate = _fixture()

    with pytest.raises(
        ValueError,
        match="derived state",
    ):
        service.record(
            person=person,
            candidate=candidate,
            decision="unreviewed",
        )


def test_non_profile_entity_cannot_be_identity_review_candidate():
    service, _source, _evidence, _links, person, candidate = _fixture()
    candidate.entity_type = EntityType.EMAIL

    with pytest.raises(
        ValueError,
        match="username/account/profile",
    ):
        service.record(
            person=person,
            candidate=candidate,
            decision="confirmed",
        )
