from app.models.entity import EntityType
from app.osint.models import OsintTargetType
from app.osint.result import OsintFinding
from app.osint.finding_persistence import OsintFindingPersistenceService


def _finding(*, category, value, url):
    return OsintFinding(
        category=category,
        value=value,
        url=url,
        source="live_web",
        confidence=0.9,
    )


def test_open_web_provenance_url_candidate_is_suppressed():
    finding = _finding(
        category="domain",
        value="example.org",
        url="https://source.example/page",
    )

    assert OsintFindingPersistenceService._is_open_web_provenance_url_candidate(
        entity_type=EntityType.URL,
        value="https://source.example/page",
        finding=finding,
        target_type=OsintTargetType.URL,
        target_value="https://target.example/",
    ) is True


def test_open_web_original_target_url_is_suppressed():
    finding = _finding(
        category="url",
        value="https://target.example/page",
        url="https://archive.example/capture",
    )

    assert OsintFindingPersistenceService._is_open_web_provenance_url_candidate(
        entity_type=EntityType.URL,
        value="https://target.example/page/",
        finding=finding,
        target_type=OsintTargetType.URL,
        target_value="https://target.example/page",
    ) is True


def test_different_explicit_discovered_url_is_kept():
    finding = _finding(
        category="url",
        value="https://new.example/profile",
        url="https://source.example/page",
    )

    assert OsintFindingPersistenceService._is_open_web_provenance_url_candidate(
        entity_type=EntityType.URL,
        value="https://new.example/profile",
        finding=finding,
        target_type=OsintTargetType.URL,
        target_value="https://target.example/page",
    ) is False


def test_non_url_entities_are_never_suppressed_by_url_rule():
    finding = _finding(
        category="phone",
        value="+1 312-996-7000",
        url="https://source.example/page",
    )

    assert OsintFindingPersistenceService._is_open_web_provenance_url_candidate(
        entity_type=EntityType.PHONE,
        value="+1 312-996-7000",
        finding=finding,
        target_type=OsintTargetType.URL,
        target_value="https://target.example/page",
    ) is False
