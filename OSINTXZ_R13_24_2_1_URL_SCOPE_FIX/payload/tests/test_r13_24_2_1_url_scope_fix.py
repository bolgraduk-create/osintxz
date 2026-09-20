from app.application.adaptive_relevance import classify_suppressed_row


def _row(seed: str, url: str):
    return {
        "seedType": "url",
        "seed": seed,
        "url": url,
        "title": url,
        "detail": "Historical URL",
        "meta": "",
        "contextRelevanceStatus": "suppressed",
        "contextRelevanceScore": 0,
        "contextMatchedTerms": [],
        "identifiers": {},
        "findingMetadata": {},
    }


def test_same_host_unrelated_account_stays_suppressed():
    result = classify_suppressed_row(
        _row("https://gitlab.com/torvalds", "https://gitlab.com/adamstoolkit")
    )
    assert result.tier == "suppressed"


def test_descendant_url_is_possible():
    result = classify_suppressed_row(
        _row("https://gitlab.com/torvalds", "https://gitlab.com/torvalds/linux")
    )
    assert result.tier == "possible"


def test_host_root_can_surface_same_host_page_as_possible():
    result = classify_suppressed_row(
        _row("https://example.com/", "https://example.com/about")
    )
    assert result.tier == "possible"


def test_other_host_is_suppressed():
    result = classify_suppressed_row(
        _row("https://gitlab.com/torvalds", "https://github.com/torvalds")
    )
    assert result.tier == "suppressed"
