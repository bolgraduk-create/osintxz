from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.person_mention_selection_service import PersonMentionSelectionService
from app.models.entity import EntityType


class FakeSession:
    def flush(self):
        return None


class FakeSourceService:
    def __init__(self):
        self.created = []

    def create_source(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.created.append(row)
        return row


class FakeEvidenceService:
    def __init__(self):
        self.rows = []
        self.repository = SimpleNamespace(session=FakeSession())

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row


class FakeLinkService:
    def __init__(self, evidence_service):
        self.evidence_service = evidence_service
        self.links = []

    def ensure_link(self, *, evidence_id, entity_id):
        key = (evidence_id, entity_id)
        created = key not in self.links
        if created:
            self.links.append(key)
        return SimpleNamespace(evidence_id=evidence_id, entity_id=entity_id), created

    def get_evidence_objects_for_entity(self, entity_id):
        evidence_ids = {evidence_id for evidence_id, linked_id in self.links if linked_id == entity_id}
        return [row for row in self.evidence_service.rows if row.id in evidence_ids]


def _service():
    evidence = FakeEvidenceService()
    links = FakeLinkService(evidence)
    return (
        PersonMentionSelectionService(
            source_service=FakeSourceService(),
            evidence_service=evidence,
            evidence_link_service=links,
        ),
        evidence,
        links,
    )


def _person():
    return SimpleNamespace(
        id=uuid4(),
        case_id=uuid4(),
        entity_type=EntityType.PERSON,
    )


def _mention():
    return {
        "title": "Linus Torvalds interview",
        "source": "example",
        "url": "https://example.org/interview",
        "detail": "Profile mentions Linux Foundation and @torvalds.",
        "mentionSummary": "Full name · Linux Foundation · torvalds",
        "mentionScore": 94,
        "mentionSignals": ["Full name", "Linux Foundation", "torvalds"],
        "lane": "federation",
        "mentionLabel": "Strong mention",
    }


def test_person_mention_selection_persists_safe_provenance_and_link():
    service, evidence_service, links = _service()
    person = _person()

    result = service.add(person=person, mention=_mention())

    assert result.duplicate is False
    assert len(evidence_service.rows) == 1
    evidence = evidence_service.rows[0]
    assert '"workflow": "person_mention_selection"' in evidence.metadata_json
    assert '"identity_verified": false' in evidence.metadata_json
    assert "Linux Foundation" in evidence.metadata_json
    assert (evidence.id, person.id) in links.links


def test_person_mention_selection_is_idempotent_for_same_person_and_mention():
    service, evidence_service, _links = _service()
    person = _person()

    first = service.add(person=person, mention=_mention())
    second = service.add(person=person, mention=_mention())

    assert first.duplicate is False
    assert second.duplicate is True
    assert len(evidence_service.rows) == 1


def test_person_mention_selection_requires_multiple_signals():
    service, _evidence, _links = _service()
    person = _person()
    mention = _mention()
    mention["mentionSignals"] = ["Full name"]

    with pytest.raises(ValueError, match="at least two"):
        service.add(person=person, mention=mention)


def test_non_http_url_is_not_persisted_as_link_scheme():
    service, evidence_service, _links = _service()
    person = _person()
    mention = _mention()
    mention["url"] = "javascript:alert(1)"

    service.add(person=person, mention=mention)

    evidence = evidence_service.rows[0]
    assert "javascript:" not in evidence.metadata_json


def test_qml_and_bridges_expose_mentions_person_action_and_card_sections():
    from pathlib import Path

    person_qml = Path("app/interface/desktop/qml/pages/Person.qml").read_text(encoding="utf-8")
    search_qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    desktop_bridge = Path("app/interface/desktop/bridges/desktop_bridge.py").read_text(encoding="utf-8")
    investigation_bridge = Path("app/interface/desktop/bridges/investigation_search_bridge.py").read_text(encoding="utf-8")

    assert "R13.23.1 PERSON CARD POLISH + MENTIONS" in person_qml
    assert 'title: "Corroborating Mentions"' in person_qml
    assert 'label: "Mentions"' in person_qml
    assert "root.reviewRows.length" in person_qml
    assert 'title: "WEB PROFILES / PAGES"' in person_qml
    assert 'title: "TECHNICAL"' in person_qml

    assert "R13.23.1 ADD MENTION TO PERSON" in search_qml
    assert 'text: "Add to person"' in search_qml
    assert "addMentionToPerson" in search_qml
    assert "personOptions" in search_qml

    assert "R13.23.1 PERSON MENTION SNAPSHOT" in desktop_bridge
    assert '"mentions": mention_rows[:40]' in desktop_bridge
    assert "R13.23.1 PERSON MENTION ACTIONS" in investigation_bridge
    assert "def addMentionToPerson" in investigation_bridge
    assert "def personOptions" in investigation_bridge
