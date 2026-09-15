from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.person_attachment_service import PersonAttachmentService
from app.models.entity import EntityType


class _Session:
    def __init__(self):
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1


class _SourceService:
    def __init__(self):
        self.rows = []

    def create_source(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row


class _EvidenceService:
    def __init__(self):
        self.rows = []
        self.repository = SimpleNamespace(session=_Session())

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(
            id=uuid4(),
            metadata_json=None,
            sha256=None,
            created_at=None,
            **kwargs,
        )
        self.rows.append(row)
        return row


class _EntityService:
    def __init__(self):
        self.rows = []

    def resolve_or_create_entity(self, **kwargs):
        for row in self.rows:
            if row.entity_type == kwargs["entity_type"] and row.value == kwargs["value"]:
                return row, False
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row, True


class _LinkService:
    def __init__(self, evidence_service):
        self.evidence_service = evidence_service
        self.links = []

    def ensure_link(self, *, evidence_id, entity_id):
        pair = (evidence_id, entity_id)
        if pair in self.links:
            return SimpleNamespace(evidence_id=evidence_id, entity_id=entity_id), False
        self.links.append(pair)
        return SimpleNamespace(evidence_id=evidence_id, entity_id=entity_id), True

    def get_evidence_objects_for_entity(self, entity_id):
        ids = {evidence_id for evidence_id, linked_id in self.links if linked_id == entity_id}
        return [row for row in self.evidence_service.rows if row.id in ids]


def _runtime():
    evidence = _EvidenceService()
    return (
        _SourceService(),
        evidence,
        _EntityService(),
        _LinkService(evidence),
    )


def _person():
    return SimpleNamespace(
        id=uuid4(),
        case_id=uuid4(),
        entity_type=EntityType.PERSON,
        value="Jane Example",
    )


def test_manual_link_is_evidence_plus_url_entity_without_verified_identity():
    source, evidence, entities, links = _runtime()
    person = _person()
    service = PersonAttachmentService(
        source_service=source,
        evidence_service=evidence,
        entity_service=entities,
        evidence_link_service=links,
    )

    first = service.add(
        person=person,
        kind="link",
        title="Main profile",
        value="https://example.org/jane#profile",
        description="Added by analyst",
    )
    duplicate = service.add(
        person=person,
        kind="link",
        value="https://example.org/jane",
    )

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert len(source.rows) == 1
    assert len(evidence.rows) == 1
    assert len(entities.rows) == 1
    assert entities.rows[0].entity_type is EntityType.URL
    assert len(links.links) == 2  # evidence -> person and evidence -> URL entity

    metadata = json.loads(evidence.rows[0].metadata_json)
    assert metadata["workflow"] == "manual_person_attachment"
    assert metadata["association_basis"] == "manual_user_assertion"
    assert metadata["identity_verified"] is False
    assert metadata["url"] == "https://example.org/jane"


def test_photo_is_copied_into_managed_storage_and_hashed(tmp_path, monkeypatch):
    source, evidence, entities, links = _runtime()
    person = _person()
    original = tmp_path / "portrait.jpg"
    original.write_bytes(b"fake-jpeg-content")
    managed = tmp_path / "managed"
    monkeypatch.setattr(PersonAttachmentService, "MANAGED_DIR", managed)

    service = PersonAttachmentService(
        source_service=source,
        evidence_service=evidence,
        entity_service=entities,
        evidence_link_service=links,
    )
    result = service.add(
        person=person,
        kind="photo",
        title="Portrait",
        value=str(original),
    )

    assert result.duplicate is False
    copied = Path(result.managed_path)
    assert copied.is_file()
    assert copied.read_bytes() == original.read_bytes()
    assert copied.parent == managed / str(person.case_id) / str(person.id)
    assert evidence.rows[0].sha256
    assert evidence.rows[0].file_path == str(copied)
    assert evidence.rows[0].mime_type == "image/jpeg"
    assert links.links == [(evidence.rows[0].id, person.id)]


def test_non_person_attachment_is_rejected():
    source, evidence, entities, links = _runtime()
    service = PersonAttachmentService(
        source_service=source,
        evidence_service=evidence,
        entity_service=entities,
        evidence_link_service=links,
    )
    company = SimpleNamespace(
        id=uuid4(), case_id=uuid4(), entity_type=EntityType.ORGANIZATION,
    )
    with pytest.raises(ValueError, match="PERSON"):
        service.add(person=company, kind="note", value="Should fail")


def test_person_qml_exposes_manual_attachment_controls():
    qml = Path("app/interface/desktop/qml/pages/Person.qml").read_text(encoding="utf-8")
    bridge = Path("app/interface/desktop/bridges/desktop_bridge.py").read_text(encoding="utf-8")

    assert 'text: "+  Add item"' in qml
    assert "desktopBridge.addPersonAttachment" in qml
    assert "Dialogs.FileDialog" in qml
    assert 'title: "Photos & Files"' in qml
    assert "desktopBridge.openManagedAttachment" in qml
    assert "def addPersonAttachment" in bridge
    assert "manual_user_assertion" in Path(
        "app/application/person_attachment_service.py"
    ).read_text(encoding="utf-8")
