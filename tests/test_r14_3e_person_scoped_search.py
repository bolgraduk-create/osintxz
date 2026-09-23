from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import json
import pytest

from app.application.person_search_attribution_service import (
    PersonSearchAttributionService,
)
from app.models.entity import EntityType


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
            session=SimpleNamespace(
                flush=lambda: None
            )
        )

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(
            id=uuid4(),
            metadata_json=None,
            **kwargs,
        )
        self.rows.append(row)
        return row


class FakeLinkService:
    def __init__(self):
        self.links = []

    def ensure_link(self, *, evidence_id, entity_id):
        key = (
            evidence_id,
            entity_id,
        )
        created = key not in self.links
        if created:
            self.links.append(key)
        return SimpleNamespace(
            evidence_id=evidence_id,
            entity_id=entity_id,
        ), created


def test_search_attribution_groups_technical_entities_under_person_without_verifying_identity():
    case_id = uuid4()
    person = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.PERSON,
        value="Target Person",
    )
    email = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.EMAIL,
        value="target@example.org",
    )
    phone = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.PHONE,
        value="+380000000000",
    )

    source = FakeSourceService()
    evidence = FakeEvidenceService()
    links = FakeLinkService()

    result = PersonSearchAttributionService(
        source_service=source,
        evidence_service=evidence,
        evidence_link_service=links,
    ).attribute(
        person=person,
        entities=[
            email,
            phone,
            email,
        ],
        search_summary={
            "seed_count": 3,
        },
    )

    assert result is not None
    assert set(result.attributed_entity_ids) == {
        str(email.id),
        str(phone.id),
    }

    metadata = json.loads(
        evidence.rows[0].metadata_json
    )
    assert metadata["workflow"] == "person_search_attribution"
    assert metadata["association_basis"] == "analyst_selected_search_target"
    assert metadata["identity_verified"] is False
    assert metadata["person_entity_id"] == str(person.id)
    assert metadata["attributed_entity_count"] == 2

    assert (
        evidence.rows[0].id,
        person.id,
    ) in links.links
    assert (
        evidence.rows[0].id,
        email.id,
    ) in links.links
    assert (
        evidence.rows[0].id,
        phone.id,
    ) in links.links


def test_search_attribution_rejects_non_person_target():
    case_id = uuid4()
    not_person = SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=EntityType.EMAIL,
        value="wrong@example.org",
    )

    with pytest.raises(
        ValueError,
        match="PERSON",
    ):
        PersonSearchAttributionService(
            source_service=FakeSourceService(),
            evidence_service=FakeEvidenceService(),
            evidence_link_service=FakeLinkService(),
        ).attribute(
            person=not_person,
            entities=[],
        )


def test_entity_directory_is_person_only_and_can_create_people():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    qml = Path(
        "app/interface/desktop/qml/pages/Entities.qml"
    ).read_text(encoding="utf-8")

    assert '"all": (EntityType.PERSON,)' in bridge
    assert 'if normalized not in {"all", "people"}:' in bridge
    assert "def createPerson(" in bridge
    assert "entity_type=EntityType.PERSON" in bridge
    assert "resolve_or_create_entity" not in bridge[
        bridge.index("def createPerson("):
        bridge.index("def renameCase(")
    ]

    for token in (
        'title: "People"',
        'primaryAction: "Add Person"',
        'sectionTitle: "People"',
        "desktopBridge.createPerson(",
        "createPersonDialog",
    ):
        assert token in qml

    for removed_category in (
        'label: "Organizations"',
        'label: "Profiles"',
        'label: "Contacts"',
        'label: "Network"',
    ):
        assert removed_category not in qml


def test_search_requires_explicit_person_scope_and_can_create_new_person():
    qml = Path(
        "app/interface/desktop/qml/pages/Search.qml"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/investigation_search_bridge.py"
    ).read_text(encoding="utf-8")

    for token in (
        'text: "SEARCH TARGET"',
        'text: "+ New Person"',
        'label: "Select person…"',
        "selectedTargetPersonId",
        "root.selectedTargetPersonId.length > 0",
        "desktopBridge.createPerson(",
        "root.reloadTargetPeople(String(result.id || \"\"))",
        "root.selectedTargetPersonId\n                    )",
    ):
        assert token in qml

    for token in (
        '@Slot("QVariantMap", str, "QVariantMap", str, result=bool)',
        "person_entity_id: str =",
        "Select the person these search results belong to.",
        "The selected person belongs to a different investigation.",
        "person_entity_id=normalized_person_id",
    ):
        assert token in bridge


def test_unified_search_worker_attributes_entities_and_all_persisted_evidence_to_person():
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    for token in (
        "PersonSearchAttributionService",
        "person_entity_id: str =",
        "parent_entity_id=person_uuid",
        "attributed_entity_ids",
        "attributed_evidence_ids",
        "_persistence_entity_ids(",
        "_persistence_evidence_ids(",
        "container.evidence_link_service.ensure_link(",
        "entity_id=person_uuid",
        '"attributedEvidenceCount"',
        '"attributionEvidenceId"',
    ):
        assert token in worker


def test_person_card_marks_search_attribution_as_context_not_confirmation():
    bridge = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")
    profile = Path(
        "app/application/unified_target_profile.py"
    ).read_text(encoding="utf-8")

    assert 'is_search_attribution = evidence_workflow == "person_search_attribution"' in bridge
    assert '"search_attributed"' in bridge
    assert '"search_attributed": "Search attributed"' in profile
    assert '"analyst_confirmed": "Analyst confirmed"' in profile
