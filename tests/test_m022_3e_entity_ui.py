from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.interface.desktop.bridges.desktop_bridge import DesktopBridge
from app.models.entity import EntityType


class _Cases:
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id

    def get_cases(self):
        return [{"id": self.case_id, "title": "Entity UI case", "description": ""}]


class _EntityService:
    def __init__(self, entities):
        self.entities = list(entities)

    def count_all(self, *, case_id=None, entity_types=()):
        rows = self._rows(case_id, entity_types)
        return len(rows)

    def count_by_type(self, *, case_id=None):
        result = {}
        for entity in self._rows(case_id, ()):
            result[entity.entity_type] = result.get(entity.entity_type, 0) + 1
        return result

    def get_page(self, *, limit=100, offset=0, case_id=None, entity_types=()):
        return self._rows(case_id, entity_types)[offset:offset + limit]

    def get_entity(self, entity_id):
        return next((row for row in self.entities if row.id == entity_id), None)

    def _rows(self, case_id, entity_types):
        rows = [row for row in self.entities if case_id is None or row.case_id == case_id]
        if entity_types:
            rows = [row for row in rows if row.entity_type in entity_types]
        return rows


class _EvidenceLinks:
    def __init__(self, evidence, associations):
        self.evidence = evidence
        self.associations = associations

    def get_evidence_objects_for_entity(self, entity_id):
        return list(self.evidence)

    def get_entities_for_evidence(self, evidence_id):
        return list(self.associations)


class _Container:
    def __init__(self, case_id, entities, evidence, associations):
        self.case_controller = _Cases(str(case_id))
        self.entity_service = _EntityService(entities)
        self.evidence_link_service = _EvidenceLinks(evidence, associations)

    def rollback(self):
        return None


def _entity(case_id, entity_type, value, *, metadata=None):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=entity_type,
        value=value,
        normalized_value=value.casefold(),
        confidence=0.92,
        metadata_json=json.dumps(metadata or {}),
        description="Entity UI fixture",
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )


def test_entity_directory_filters_on_backend_types_and_exposes_counts():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane Example")
    company = _entity(case_id, EntityType.ORGANIZATION, "Example LLC")
    url = _entity(case_id, EntityType.URL, "https://example.org/profile")
    bridge = DesktopBridge(_Container(case_id, [person, company, url], [], []))
    assert bridge.selectCase(str(case_id))

    counts = bridge.entityCategoryCounts
    assert counts["all"] == 3
    assert counts["people"] == 1
    assert counts["organizations"] == 1
    assert counts["links"] == 1

    assert bridge.setEntityCategory("people")
    rows = bridge.pageData("entities", "")["records"]
    assert [row["entityType"] for row in rows] == ["person"]
    assert rows[0]["interactive"] is True


def test_person_page_surfaces_only_explicit_links_from_shared_evidence():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane Example")
    profile = _entity(
        case_id,
        EntityType.USERNAME,
        "jane_example",
        metadata={"connector": "Sherlock", "finding_url": "https://example.org/jane_example"},
    )
    evidence = SimpleNamespace(
        id=uuid4(),
        evidence_type=SimpleNamespace(value="other"),
        title="Sherlock profile finding",
        description="Profile discovered by connector",
        value="jane_example",
        metadata_json=json.dumps({"finding": {"url": "https://example.org/jane_example"}}),
        created_at=None,
    )
    associations = [
        SimpleNamespace(entity_id=person.id),
        SimpleNamespace(entity_id=profile.id),
    ]
    bridge = DesktopBridge(_Container(case_id, [person, profile], [evidence], associations))
    bridge.selectCase(str(case_id))

    assert bridge.openEntity(str(person.id))
    snapshot = bridge.currentEntity
    assert snapshot["title"] == "Jane Example"
    assert snapshot["links"][0]["url"] == "https://example.org/jane_example"
    assert snapshot["relatedEntities"][0]["value"] == "jane_example"
    assert "does not by itself prove account ownership" in snapshot["associationNotice"]


def test_dashboard_and_entity_qml_have_real_navigation_contracts():
    dashboard = Path("app/interface/desktop/qml/pages/Dashboard.qml").read_text(encoding="utf-8")
    entities = Path("app/interface/desktop/qml/pages/Entities.qml").read_text(encoding="utf-8")
    person = Path("app/interface/desktop/qml/pages/Person.qml").read_text(encoding="utf-8")
    main = Path("app/interface/desktop/qml/Main.qml").read_text(encoding="utf-8")
    registry = Path("app/interface/desktop/qml/pages/Registry.qml").read_text(encoding="utf-8")

    assert 'desktopBridge.navigateTo("cases")' in dashboard
    assert 'desktopBridge.navigateTo("entities")' in dashboard
    assert 'desktopBridge.navigateTo("evidence")' in dashboard
    assert "desktopBridge.openCase(caseId)" in dashboard
    assert "desktopBridge.setEntityCategory(categoryKey)" in entities
    assert 'case "person": return "pages/Person.qml"' in main
    assert "desktopBridge.openExternalUrl" in person
    assert "Layout.maximumHeight: 78" in registry
