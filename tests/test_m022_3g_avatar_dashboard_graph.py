from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.application.person_attachment_service import PersonAttachmentService
from app.interface.desktop.bridges.desktop_bridge import DesktopBridge
from app.models.entity import EntityType


class _Cases:
    def __init__(self, case_id):
        self.case_id = case_id

    def get_cases(self):
        return [{"id": str(self.case_id), "title": "Graph case", "description": ""}]


class _Entities:
    def __init__(self, rows):
        self.rows = list(rows)

    def count_all(self, *, case_id=None, entity_types=()):
        return len(self._rows(case_id, entity_types))

    def count_by_type(self, *, case_id=None):
        result = {}
        for row in self._rows(case_id, ()):
            result[row.entity_type] = result.get(row.entity_type, 0) + 1
        return result

    def get_page(self, *, limit=100, offset=0, case_id=None, entity_types=()):
        return self._rows(case_id, entity_types)[offset: offset + limit]

    def get_entity(self, entity_id):
        return next((row for row in self.rows if row.id == entity_id), None)

    def _rows(self, case_id, entity_types):
        rows = [row for row in self.rows if case_id is None or row.case_id == case_id]
        if entity_types:
            rows = [row for row in rows if row.entity_type in entity_types]
        return rows


class _Links:
    def __init__(self, photos):
        self.photos = photos

    def get_image_evidence_for_entity(self, entity_id):
        return list(self.photos.get(entity_id, []))

    def get_evidence_objects_for_entity(self, entity_id):
        return []


class _Graph:
    def __init__(self, payload):
        self.payload = payload

    def get_case_graph_data(self, case_id):
        return self.payload


class _Container:
    def __init__(self, case_id, entities, graph, photos):
        self.case_controller = _Cases(case_id)
        self.entity_service = _Entities(entities)
        self.entity_graph_service = _Graph(graph)
        self.evidence_link_service = _Links(photos)

    def rollback(self):
        return None


def _entity(case_id, entity_type, value):
    return SimpleNamespace(
        id=uuid4(),
        case_id=case_id,
        entity_type=entity_type,
        value=value,
        normalized_value=value.casefold(),
        confidence=1.0,
        metadata_json="{}",
        description="fixture",
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )


def test_entity_directory_person_row_uses_latest_managed_photo(tmp_path, monkeypatch):
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane Example")
    managed_root = tmp_path / "person_attachments"
    person_dir = managed_root / str(case_id) / str(person.id)
    person_dir.mkdir(parents=True)
    photo_path = person_dir / "portrait.jpg"
    photo_path.write_bytes(b"image fixture")
    monkeypatch.setattr(PersonAttachmentService, "MANAGED_DIR", managed_root)

    evidence = SimpleNamespace(file_path=str(photo_path), created_at=None)
    graph = {"nodes": [], "edges": [], "statistics": {}}
    bridge = DesktopBridge(_Container(case_id, [person], graph, {person.id: [evidence]}))
    assert bridge.selectCase(str(case_id))

    row = bridge.pageData("entities", "")["records"][0]
    assert row["entityType"] == "person"
    assert row["avatarUrl"].startswith("file:")
    assert "portrait.jpg" in row["avatarUrl"]


def test_home_focus_is_person_only_not_arbitrary_case_entity():
    case_id = uuid4()
    person = _entity(case_id, EntityType.PERSON, "Jane Example")
    email = _entity(case_id, EntityType.EMAIL, "jane@example.org")
    graph = {
        "nodes": [
            {"id": str(person.id), "label": person.value, "type": "person", "degree": 1},
            {"id": str(email.id), "label": email.value, "type": "email", "degree": 1},
        ],
        "edges": [{"source": str(person.id), "target": str(email.id), "type": "emailed"}],
        "statistics": {},
    }
    bridge = DesktopBridge(_Container(case_id, [person, email], graph, {}))
    assert bridge.selectCase(str(case_id))

    dashboard = bridge.dashboard
    assert dashboard["graphFocusId"] == str(person.id)
    assert [row["id"] for row in dashboard["graphOptions"]] == [str(person.id)]
    assert bridge.selectDashboardEntity(str(email.id)) is False


def test_qml_uses_circular_avatars_and_simple_person_home_card():
    components = Path("app/interface/desktop/qml/components")
    pages = Path("app/interface/desktop/qml/pages")

    circular = (components / "CircularAvatar.qml").read_text(encoding="utf-8")
    panel = (components / "Panel.qml").read_text(encoding="utf-8")
    person = (pages / "Person.qml").read_text(encoding="utf-8")
    workspace = (pages / "DataWorkspace.qml").read_text(encoding="utf-8")
    dashboard = (pages / "Dashboard.qml").read_text(encoding="utf-8")

    assert "import QtQuick.Effects" in circular
    assert "MultiEffect" in circular
    assert "maskEnabled: true" in circular
    assert "CircularAvatar" in person
    assert "CircularAvatar" in workspace
    assert "recordRow.modelData.avatarUrl" in workspace
    assert 'root.subtitle === "" ? Spacing.panelHeader' in panel
    assert 'text: "PERSON"' in dashboard
    assert 'text: "Open Person"' in dashboard
    assert 'text: "Full Graph"' in dashboard
    assert "personSummary" in dashboard
    assert 'text: "PATH"' not in dashboard
    assert "setDashboardGraphDepth" not in dashboard
