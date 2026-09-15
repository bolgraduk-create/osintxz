from types import SimpleNamespace
import pytest

from app.models.entity import EntityType
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)


@pytest.mark.parametrize("category", ["phone_metadata", "metadata", "search_query"])
def test_non_identifier_finding_does_not_create_empty_url(category):
    finding = SimpleNamespace(category=category, value="local metadata", url="", confidence=0.5)
    assert OsintFindingPersistenceService._entity_candidates(finding) == ()


def test_explicit_lead_metadata_does_not_promote_navigation_url():
    finding = SimpleNamespace(
        category="search_query", value="phone", url="https://example.org/search?q=phone",
        confidence=0.5, metadata={"lead_only": True},
    )
    assert OsintFindingPersistenceService._entity_candidates(finding) == ()


def test_search_query_url_is_not_entity_candidate():
    finding = SimpleNamespace(
        category="search_query",
        value="+380631234567",
        url=(
            "https://www.google.com/search?"
            "q=site%3Afacebook.com+380631234567"
        ),
        confidence=0.5,
    )

    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(finding)
    )

    assert not any(
        entity_type is EntityType.URL
        and "google.com/search" in value
        for entity_type, value, _ in candidates
    )


def test_real_url_finding_still_becomes_entity():
    finding = SimpleNamespace(
        category="url",
        value="https://example.com/profile",
        url="",
        confidence=0.8,
    )

    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(finding)
    )

    assert any(
        entity_type is EntityType.URL
        and value == "https://example.com/profile"
        for entity_type, value, _ in candidates
    )


def test_account_profile_url_still_becomes_entity():
    finding = SimpleNamespace(
        category="account",
        value="example_user",
        url="https://example.com/example_user",
        confidence=1.0,
    )

    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(finding)
    )

    assert any(
        entity_type is EntityType.URL
        and value == "https://example.com/example_user"
        for entity_type, value, _ in candidates
    )
