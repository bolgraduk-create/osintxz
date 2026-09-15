from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.application.person_profile_selection_service import PersonProfileSelectionService
from app.interface.desktop.bridges.desktop_bridge import DesktopBridge
from app.models.entity import EntityType


class _Session:
    def flush(self):
        return None


class _Sources:
    def __init__(self):
        self.rows = []

    def create_source(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row


class _Evidence:
    def __init__(self):
        self.rows = []
        self.repository = SimpleNamespace(session=_Session())

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), metadata_json=None, **kwargs)
        self.rows.append(row)
        return row


class _EvidenceLinks:
    def __init__(self, evidence=None):
        self.evidence = evidence
        self.links = []

    def ensure_link(self, *, evidence_id, entity_id):
        pair = (evidence_id, entity_id)
        created = pair not in self.links
        if created:
            self.links.append(pair)
        return SimpleNamespace(evidence_id=evidence_id, entity_id=entity_id), created

    def get_evidence_objects_for_entity(self, entity_id):
        if self.evidence is None:
            return []
        ids = {evidence_id for evidence_id, linked_id in self.links if linked_id == entity_id}
        return [row for row in self.evidence.rows if row.id in ids]

    def get_entities_for_evidence(self, evidence_id):
        return [
            SimpleNamespace(entity_id=entity_id)
            for linked_evidence_id, entity_id in self.links
            if linked_evidence_id == evidence_id
        ]

    def get_image_evidence_for_entity(self, entity_id):
        return []


class _Cases:
    def __init__(self, case_id):
        self.case_id = case_id

    def get_cases(self):
        return [{"id": str(self.case_id), "title": "Case", "description": ""}]


class _Entities:
    def __init__(self, rows):
        self.rows = list(rows)

    def count_all(self, *, case_id=None, entity_types=()):
        return len(self._filtered(case_id, entity_types))

    def count_by_type(self, *, case_id=None):
        result = {}
        for row in self._filtered(case_id, ()):
            result[row.entity_type] = result.get(row.entity_type, 0) + 1
        return result

    def get_page(self, *, limit=100, offset=0, case_id=None, entity_types=()):
        return self._filtered(case_id, entity_types)[offset: offset + limit]

    def get_entity(self, entity_id):
        return next((row for row in self.rows if row.id == entity_id), None)

    def _filtered(self, case_id, entity_types):
        rows = [row for row in self.rows if case_id is None or row.case_id == case_id]
        if entity_types:
            rows = [row for row in rows if row.entity_type in entity_types]
        return rows


class _Container:
    def __init__(self, case_id, entities):
        self.case_controller = _Cases(case_id)
        self.entity_service = _Entities(entities)
        self.evidence_link_service = _EvidenceLinks()

    def rollback(self):
        return None


def _entity(case_id, entity_type, value, *, metadata=None):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=entity_type,
        value=value,
        normalized_value=value.casefold(),
        confidence=0.91,
        metadata_json=json.dumps(metadata or {}),
        description="fixture",
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )


def test_profile_selection_records_explicit_unverified_association():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane")
    candidate = _entity(
        case_id,
        EntityType.USERNAME,
        "janex",
        metadata={
            "workflow": "osint_enrichment",
            "connector": "Sherlock",
            "evidence_id": str(uuid4()),
            "source_id": str(uuid4()),
            "finding_url": "https://example.test/janex",
        },
    )
    sources = _Sources()
    evidence = _Evidence()
    links = _EvidenceLinks(evidence=evidence)
    service = PersonProfileSelectionService(
        source_service=sources,
        evidence_service=evidence,
        evidence_link_service=links,
    )

    first = service.add(person=person, candidate=candidate)
    duplicate = service.add(person=person, candidate=candidate)

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert len(sources.rows) == 1
    assert len(evidence.rows) == 1
    assert set(links.links) == {
        (evidence.rows[0].id, person.id),
        (evidence.rows[0].id, candidate.id),
    }
    metadata = json.loads(evidence.rows[0].metadata_json)
    assert metadata["workflow"] == "person_profile_selection"
    assert metadata["association_basis"] == "analyst_selected_existing_intelligence"
    assert metadata["identity_verified"] is False
    assert metadata["selected_entity_id"] == str(candidate.id)


def test_person_snapshot_offers_stored_osint_candidates_only():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane")
    osint_username = _entity(
        case_id,
        EntityType.USERNAME,
        "janex",
        metadata={"workflow": "osint_enrichment", "connector": "Sherlock", "evidence_id": str(uuid4())},
    )
    unrelated_manual = _entity(case_id, EntityType.EMAIL, "manual@example.test", metadata={})
    bridge = DesktopBridge(_Container(case_id, [person, osint_username, unrelated_manual]))
    assert bridge.selectCase(str(case_id))
    assert bridge.openEntity(str(person.id))

    candidates = bridge.currentEntity["profileCandidates"]
    assert [row["id"] for row in candidates] == [str(osint_username.id)]
    assert candidates[0]["connector"] == "Sherlock"


def test_person_graph_contains_person_and_accounts_only():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane")
    bridge = DesktopBridge(_Container(case_id, [person]))

    payload = bridge._person_graph_payload(
        person,
        related_rows=[
            {"id": str(uuid4()), "rawType": "username", "value": "janex", "basis": "analyst_selected"},
            {"id": str(uuid4()), "rawType": "account", "value": "telegram:123", "basis": "manual"},
            {"id": str(uuid4()), "rawType": "email", "value": "jane@example.test", "basis": "manual"},
            {"id": str(uuid4()), "rawType": "phone", "value": "+380000000000", "basis": "manual"},
            {"id": str(uuid4()), "rawType": "url", "value": "https://example.test", "basis": "manual"},
        ],
    )

    assert [row["type"] for row in payload["nodes"]] == ["person", "username", "account"]
    assert len(payload["edges"]) == 2
    assert all(row["type"] == "profile_account" for row in payload["edges"])


def test_qml_exposes_candidate_picker_and_home_profile_web():
    pages = Path("app/interface/desktop/qml/pages")
    components = Path("app/interface/desktop/qml/components")
    bridge = Path("app/interface/desktop/bridges/desktop_bridge.py").read_text(encoding="utf-8")
    person = (pages / "Person.qml").read_text(encoding="utf-8")
    dashboard = (pages / "Dashboard.qml").read_text(encoding="utf-8")
    entity_web = (components / "EntityWeb.qml").read_text(encoding="utf-8")

    assert 'text: "+  From intelligence"' in person
    assert "profileCandidates" in person
    assert "desktopBridge.addExistingDataToPerson" in person
    assert 'title: "Profiles & Accounts"' in person
    assert 'title: "Account Map"' not in person
    assert "EntityWeb" not in person
    assert "EntityWeb" in dashboard
    assert 'text: "PERSON"' in dashboard
    assert 'text: "Full Graph"' in dashboard
    assert 'text: "PATH"' not in dashboard
    assert "setDashboardPathEndpoint" not in dashboard
    assert "property bool showTypeLabels" in entity_web
    assert "def addExistingDataToPerson" in bridge
