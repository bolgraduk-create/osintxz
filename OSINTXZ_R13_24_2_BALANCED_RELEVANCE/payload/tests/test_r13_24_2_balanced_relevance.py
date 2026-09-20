from app.application.adaptive_relevance import classify_suppressed_row


def _row(seed_type, seed, *, title="", detail="", url="", row_type="finding", metadata=None, identifiers=None):
    return {
        "seedType": seed_type,
        "seed": seed,
        "title": title,
        "detail": detail,
        "url": url,
        "type": row_type,
        "lane": "Classic OSINT",
        "findingMetadata": metadata or {},
        "identifiers": identifiers or {},
        "contextRelevanceStatus": "low_relevance",
        "contextRelevanceScore": 8,
        "contextMatchedTerms": [],
    }


def test_username_with_real_text_relation_is_possible():
    item = classify_suppressed_row(_row(
        "username", "texnobreath",
        title="Profile mention @texnobreath",
        detail="Public account reference",
    ))
    assert item.tier == "possible"
    assert item.score >= 50


def test_username_positive_account_observation_without_url_is_possible():
    item = classify_suppressed_row(_row(
        "username", "texnobreath",
        title="Instagram",
        detail="Account observation",
        row_type="account",
        metadata={"registration_confirmed": True, "service": "instagram"},
    ))
    assert item.tier == "possible"


def test_username_in_non_owner_url_is_possible_but_not_unrelated_url():
    related = classify_suppressed_row(_row(
        "username", "texnobreath",
        title="Historical page",
        url="https://example.org/search/users/texnobreath/activity",
        row_type="historical_url",
    ))
    assert related.tier == "possible"

    unrelated = classify_suppressed_row(_row(
        "username", "texnobreath",
        title="Historical page",
        url="https://gitlab.com/adamstoolkit",
        row_type="historical_url",
    ))
    assert unrelated.tier == "suppressed"


def test_negative_username_observation_stays_suppressed():
    item = classify_suppressed_row(_row(
        "username", "texnobreath",
        title="texnobreath",
        row_type="account",
        metadata={"available": True, "service": "fixture"},
    ))
    assert item.tier == "suppressed"


def test_url_same_host_can_be_possible_but_other_host_is_suppressed():
    same_host = classify_suppressed_row(_row(
        "url", "https://example.com/torvalds",
        title="Archived page",
        url="https://example.com/other/path",
    ))
    assert same_host.tier == "possible"

    other_host = classify_suppressed_row(_row(
        "url", "https://example.com/torvalds",
        title="Archived page",
        url="https://unrelated.example.net/other/path",
    ))
    assert other_host.tier == "suppressed"


def test_domain_subdomain_relation_is_possible():
    item = classify_suppressed_row(_row(
        "domain", "example.com",
        title="Observed host",
        url="https://api.example.com/v1/status",
    ))
    assert item.tier == "possible"


def test_hash_requires_identifier_itself_to_be_visible():
    seed = "0123456789abcdef0123456789abcdef"
    visible = classify_suppressed_row(_row(
        "hash", seed,
        detail=f"Sample hash {seed}",
    ))
    assert visible.tier == "possible"

    unrelated = classify_suppressed_row(_row(
        "hash", seed,
        detail="Different sample",
    ))
    assert unrelated.tier == "suppressed"
