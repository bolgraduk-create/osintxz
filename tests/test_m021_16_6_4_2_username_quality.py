from app.models.entity import EntityType
from app.osint.finding_persistence import OsintFindingPersistenceService
from app.osint.result import OsintFinding
from app.osint.username_quality import UsernameFindingKind, UsernameFindingQuality


def test_proton_endpoint_is_not_profile():
    result = UsernameFindingQuality.classify(
        category="account",
        value="wixxlexx",
        url="https://account.proton.me",
        target_username="wixxlexx",
    )
    assert result.kind is UsernameFindingKind.SERVICE_ENDPOINT


def test_telegram_profile_is_profile():
    result = UsernameFindingQuality.classify(
        category="account",
        value="wixxlexx",
        url="https://t.me/wixxlexx/",
        target_username="wixxlexx",
    )
    assert result.kind is UsernameFindingKind.PUBLIC_PROFILE
    assert result.canonical_profile_url == "https://t.me/wixxlexx"


def test_tiktok_profile_is_profile():
    result = UsernameFindingQuality.classify(
        category="account",
        value="wixxlexx",
        url="https://www.tiktok.com/@wixxlexx/",
        target_username="wixxlexx",
    )
    assert result.kind is UsernameFindingKind.PUBLIC_PROFILE


def test_roblox_profile_is_profile():
    result = UsernameFindingQuality.classify(
        category="account",
        value="wixxlexx",
        url="https://www.roblox.com/users/4906943378",
        target_username="wixxlexx",
    )
    assert result.kind is UsernameFindingKind.PUBLIC_PROFILE


def test_account_entity_is_suppressed_but_profile_url_kept():
    finding = OsintFinding(
        category="account",
        value="wixxlexx",
        url="https://t.me/wixxlexx",
        confidence=0.9,
    )

    candidates = OsintFindingPersistenceService._entity_candidates(finding)
    filtered = OsintFindingPersistenceService._username_quality_candidates(
        finding=finding,
        target_value="wixxlexx",
        candidates=candidates,
    )

    assert all(item[0] is not EntityType.ACCOUNT for item in filtered)
    assert any(
        item[0] is EntityType.URL and item[1] == "https://t.me/wixxlexx"
        for item in filtered
    )


def test_service_endpoint_creates_no_entity_candidate():
    finding = OsintFinding(
        category="account",
        value="wixxlexx",
        url="https://account.proton.me",
        confidence=0.9,
    )

    candidates = OsintFindingPersistenceService._entity_candidates(finding)
    filtered = OsintFindingPersistenceService._username_quality_candidates(
        finding=finding,
        target_value="wixxlexx",
        candidates=candidates,
    )

    assert filtered == ()
