from __future__ import annotations

from app.interface.desktop.bridges.desktop_bridge import DesktopBridge
from app.models.entity import EntityType


def test_entity_paging_uses_person_filter_when_service_supports_it():
    calls = []

    def modern_get_page(*, limit, offset, case_id, entity_types=()):
        calls.append(entity_types)
        return []

    result = DesktopBridge._call_entity_service_with_optional_type_filter(
        modern_get_page,
        entity_types=(EntityType.PERSON,),
        limit=100,
        offset=0,
        case_id=None,
    )

    assert result == []
    assert calls == [(EntityType.PERSON,)]


def test_entity_paging_falls_back_only_for_legacy_signature():
    calls = []

    def legacy_get_page(*, limit, offset, case_id):
        calls.append((limit, offset, case_id))
        return ["legacy-row"]

    result = DesktopBridge._call_entity_service_with_optional_type_filter(
        legacy_get_page,
        entity_types=(EntityType.PERSON,),
        limit=100,
        offset=0,
        case_id=None,
    )

    assert result == ["legacy-row"]
    assert calls == [(100, 0, None)]


def test_entity_paging_does_not_hide_unrelated_type_errors():
    def broken_get_page(*, limit, offset, case_id, entity_types=()):
        raise TypeError("internal conversion failed")

    try:
        DesktopBridge._call_entity_service_with_optional_type_filter(
            broken_get_page,
            entity_types=(EntityType.PERSON,),
            limit=100,
            offset=0,
            case_id=None,
        )
    except TypeError as exc:
        assert str(exc) == "internal conversion failed"
    else:
        raise AssertionError("Unrelated TypeError must not be swallowed")
