from __future__ import annotations

from pathlib import Path

from app.application.browser_account_verification import (
    BrowserProfileCandidate,
    BrowserVerificationResult,
    BrowserVerificationSummary,
    annotate_browser_account_validation,
    assess_rendered_profile,
)
from app.application.investigation_result_consolidation import (
    consolidate_result_rows,
)
from app.application.search_quality_engine import assess_search_quality_row


def _candidate(**overrides) -> BrowserProfileCandidate:
    data = {
        "url": "https://example.test/users/wixxlexx",
        "username": "wixxlexx",
        "source": "Sherlock",
        "service": "Example",
        "provider_corroboration": 1,
    }
    data.update(overrides)
    return BrowserProfileCandidate(**data)


def _row(**overrides) -> dict:
    row = {
        "lane": "Classic OSINT",
        "source": "Sherlock",
        "service": "Example",
        "title": "wixxlexx",
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": "https://example.test/users/wixxlexx",
        "seed": "wixxlexx",
        "seedType": "username",
        "identifiers": {"username": "wixxlexx"},
        "findingMetadata": {
            "provider_reported_claimed": True,
            "registration_confirmed": False,
            "requires_account_verification": True,
        },
        "accountVerificationStatus": "reported",
        "accountVerificationReason": "HTTP pass was inconclusive.",
        "accountVerificationChecked": True,
        "confidence": 0.97,
        "reliability": 0.93,
        "candidateOnly": False,
        "depth": 0,
    }
    row.update(overrides)
    return row


def test_rendered_spa_username_on_profile_url_is_likely_not_invalid():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/users/wixxlexx",
        title="Community",
        visible_text="Welcome wixxlexx",
    )

    assert result.status == "likely"
    assert result.username_seen is True
    assert result.negative_signal == ""


def test_rendered_profile_specific_page_is_verified():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/users/wixxlexx",
        title="wixxlexx — Example",
        visible_text="wixxlexx Followers 120 Following 40 Posts 18",
        canonical="https://example.test/users/wixxlexx",
        meta={"og:type": "profile"},
    )

    assert result.status == "verified"
    assert result.evidence_score >= 55
    assert any("profile" in signal.casefold() for signal in result.evidence_signals)


def test_rendered_soft_404_is_invalid():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/users/wixxlexx",
        title="User not found",
        visible_text="This user does not exist.",
    )

    assert result.status == "invalid"
    assert result.negative_signal


def test_rendered_generic_redirect_is_invalid_only_with_direct_evidence():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/",
        title="Example community",
        visible_text="Welcome to Example",
    )

    assert result.status == "invalid"
    assert result.negative_signal == "generic_redirect"


def test_rendered_captcha_is_blocked_not_invalid():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/users/wixxlexx",
        title="Checking your browser",
        visible_text="Verify you are human before continuing",
    )

    assert result.status == "blocked"
    assert result.status != "invalid"


def test_rendered_reachable_page_without_evidence_is_uncertain():
    result = assess_rendered_profile(
        candidate=_candidate(),
        status_code=200,
        final_url="https://example.test/users/wixxlexx",
        title="Example",
        visible_text="Welcome to our community",
    )

    assert result.status == "uncertain"


class _FakeBrowserVerifier:
    def __init__(self, result: BrowserVerificationResult) -> None:
        self.result = result
        self.calls = []

    def verify(
        self,
        candidates,
        *,
        max_checks,
        navigation_timeout,
        max_concurrency,
    ):
        candidates = list(candidates)
        self.calls.append(
            {
                "candidates": candidates,
                "max_checks": max_checks,
                "navigation_timeout": navigation_timeout,
                "max_concurrency": max_concurrency,
            }
        )
        mapping = {
            "https://example.test/users/wixxlexx": self.result,
        }
        summary = BrowserVerificationSummary(
            available=True,
            checked=1 if self.result.checked else 0,
            verified=1 if self.result.status == "verified" else 0,
            likely=1 if self.result.status == "likely" else 0,
            uncertain=1 if self.result.status == "uncertain" else 0,
            blocked=1 if self.result.status == "blocked" else 0,
            invalid=1 if self.result.status == "invalid" else 0,
            unavailable=1 if self.result.status == "unavailable" else 0,
        )
        return mapping, summary


def test_consolidation_preserves_legacy_account_rows_without_validation_annotations():
    row = _row()
    row.pop("accountVerificationStatus", None)
    row.pop("accountVerificationReason", None)
    row.pop("accountVerificationChecked", None)

    result = consolidate_result_rows(
        [row],
        seeds=[{"kind": "username", "value": "wixxlexx"}],
    )

    assert len(result.rows) == 1
    assert len(result.related_accounts) == 1
    assert result.possible_rows == []


def test_non_username_account_relation_is_not_forced_through_browser_validation():
    row = {
        "lane": "Federation",
        "source": "github_public_user",
        "title": "Linus Torvalds",
        "type": "public_user",
        "seed": "Linus Torvalds",
        "seedType": "person_name",
        "candidateOnly": True,
        "identityCandidateEligible": True,
        "identityMatchScore": 100.0,
        "identityMatchReason": "full_name_match",
        "_identitySignals": {
            "names": ["Linus Torvalds"],
            "usernames": ["torvalds"],
        },
        "contextRelevanceStatus": "relevant",
        "contextRelevanceScore": 100.0,
        "contextRelevanceKeepClean": True,
        "contextRelevancePivotAllowed": False,
    }

    result = consolidate_result_rows([row])

    assert {item["title"] for item in result.related_accounts} == {
        "Linus Torvalds"
    }


def test_browser_likely_promotes_reported_account_without_claiming_verified():
    verifier = _FakeBrowserVerifier(
        BrowserVerificationResult(
            status="likely",
            reason="Rendered username is visible on the expected profile URL.",
            checked=True,
            final_url="https://example.test/users/wixxlexx",
            http_status=200,
            title="Community",
            username_seen=True,
            evidence_score=40,
            evidence_signals=("Rendered visible text contains searched username",),
        )
    )

    rows, summary = annotate_browser_account_validation(
        [_row()],
        verifier=verifier,
    )

    assert summary.likely == 1
    assert rows[0]["accountVerificationStatus"] == "likely"
    assert rows[0]["accountBrowserVerificationStatus"] == "likely"

    consolidated = consolidate_result_rows(
        rows,
        seeds=[{"kind": "username", "value": "wixxlexx"}],
    )
    assert len(consolidated.rows) == 1
    assert len(consolidated.related_accounts) == 1
    assert consolidated.related_accounts[0]["accountVerificationStatus"] == "likely"

    quality = assess_search_quality_row(rows[0])
    assert quality.would_explore is False
    assert quality.would_persist is False


def test_browser_uncertain_keeps_account_for_possible_review():
    verifier = _FakeBrowserVerifier(
        BrowserVerificationResult(
            status="uncertain",
            reason="Rendered page is reachable but inconclusive.",
            checked=True,
            final_url="https://example.test/users/wixxlexx",
            http_status=200,
        )
    )

    rows, _summary = annotate_browser_account_validation(
        [_row()],
        verifier=verifier,
    )
    consolidated = consolidate_result_rows(
        rows,
        seeds=[{"kind": "username", "value": "wixxlexx"}],
    )

    assert consolidated.rows == []
    assert consolidated.related_accounts == []
    assert len(consolidated.possible_rows) == 1
    assert consolidated.possible_rows[0]["accountVerificationStatus"] == "uncertain"


def test_browser_invalid_remains_out_of_clean_account_views():
    verifier = _FakeBrowserVerifier(
        BrowserVerificationResult(
            status="invalid",
            reason="Rendered page says user not found.",
            checked=True,
            final_url="https://example.test/users/wixxlexx",
            http_status=200,
            negative_signal="user not found",
        )
    )

    rows, _summary = annotate_browser_account_validation(
        [_row()],
        verifier=verifier,
    )
    consolidated = consolidate_result_rows(
        rows,
        seeds=[{"kind": "username", "value": "wixxlexx"}],
    )

    assert consolidated.rows == []
    assert consolidated.related_accounts == []


def test_browser_layer_is_optional_and_memory_only_by_contract():
    source = Path(
        "app/application/browser_account_verification.py"
    ).read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'crawlee[playwright]' in pyproject
    assert "MemoryStorageClient" in source
    assert 'browser_type="chromium"' in source
    assert 'max_requests_per_crawl=len(candidates)' in source
    assert "accountBrowserVerificationStatus" in source


def test_worker_runs_browser_verifier_after_http_validation():
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    http_pos = source.index("annotate_account_profile_validation(")
    browser_pos = source.index("annotate_browser_account_validation(")
    quality_pos = source.index("annotate_search_quality_rows(")

    assert http_pos < browser_pos < quality_pos
    assert '"browserAccountValidationSummary"' in source
    assert '"browserLikely"' in source


def test_account_details_exposes_browser_verification_signals():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )

    assert "BROWSER VERIFICATION" in qml
    assert "accountBrowserVerificationStatus" in qml
    assert "accountBrowserVerificationEvidenceSignals" in qml
    assert "accountBrowserVerificationTitle" in qml
