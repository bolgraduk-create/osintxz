from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.account_profile_validation import (
    ProfileFetchResult,
    annotate_account_profile_validation,
)
from app.application.contextual_relevance import assess_result_row
from app.application.search_quality_engine import assess_search_quality_row
from app.application.unified_persistence_relevance import (
    UnifiedFindingPersistenceGate,
)
from app.osint.models import OsintTargetType


def _account(
    *,
    source: str = "Sherlock",
    url: str = "https://example.test/users/wixxlexx",
    metadata: dict | None = None,
) -> dict:
    return {
        "lane": "Classic OSINT",
        "source": source,
        "service": "Example",
        "title": "wixxlexx",
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": url,
        "seed": "wixxlexx",
        "seedType": "username",
        "identifiers": {"username": "wixxlexx"},
        "findingMetadata": metadata or {
            "provider_reported_claimed": True,
            "registration_confirmed": False,
            "requires_account_verification": True,
        },
        "confidence": 0.97,
        "reliability": 0.93,
        "candidateOnly": False,
        "depth": 0,
    }


def test_live_profile_with_username_is_verified():
    def fetcher(url, timeout, max_bytes):
        del timeout, max_bytes
        return ProfileFetchResult(
            status_code=200,
            final_url=url,
            body="<html><title>wixxlexx profile</title><h1>@wixxlexx</h1></html>",
        )

    rows, summary = annotate_account_profile_validation(
        [_account()],
        fetcher=fetcher,
        max_live_checks=4,
    )

    assert rows[0]["accountVerificationStatus"] == "verified"
    assert rows[0]["accountVerificationHttpStatus"] == 200
    assert summary.verified == 1
    assert summary.invalid == 0


def test_http_404_is_invalid_and_not_clean_relevant():
    def fetcher(url, timeout, max_bytes):
        del timeout, max_bytes
        return ProfileFetchResult(
            status_code=404,
            final_url=url,
            body="Not found",
        )

    rows, summary = annotate_account_profile_validation(
        [_account()],
        fetcher=fetcher,
    )
    row = rows[0]

    assert row["accountVerificationStatus"] == "invalid"
    assert summary.invalid == 1

    relevance = assess_result_row(row)
    assert relevance.status == "contradictory"
    assert relevance.keep_clean is False
    assert relevance.pivot_allowed is False

    quality = assess_search_quality_row(row)
    assert quality.tier == "noise"
    assert quality.hard_reject_reason
    assert quality.would_show is False
    assert quality.would_explore is False
    assert quality.would_persist is False


def test_generic_redirect_away_from_username_is_invalid():
    def fetcher(url, timeout, max_bytes):
        del url, timeout, max_bytes
        return ProfileFetchResult(
            status_code=200,
            final_url="https://example.test/",
            body="<html><title>Example community</title></html>",
        )

    rows, _summary = annotate_account_profile_validation(
        [_account()],
        fetcher=fetcher,
    )

    assert rows[0]["accountVerificationStatus"] == "invalid"
    assert "redirected away" in rows[0]["accountVerificationReason"].casefold()


def test_explicit_profile_not_found_page_is_invalid_even_with_http_200():
    def fetcher(url, timeout, max_bytes):
        del timeout, max_bytes
        return ProfileFetchResult(
            status_code=200,
            final_url=url,
            body="<html><h1>User not found</h1><p>Please search again.</p></html>",
        )

    rows, _summary = annotate_account_profile_validation(
        [_account()],
        fetcher=fetcher,
    )

    assert rows[0]["accountVerificationStatus"] == "invalid"
    assert rows[0]["accountVerificationNotFoundMarker"]


def test_403_is_unreachable_not_false_negative():
    def fetcher(url, timeout, max_bytes):
        del timeout, max_bytes
        return ProfileFetchResult(
            status_code=403,
            final_url=url,
            body="Access denied",
        )

    rows, summary = annotate_account_profile_validation(
        [_account()],
        fetcher=fetcher,
    )

    assert rows[0]["accountVerificationStatus"] == "unreachable"
    assert summary.unreachable == 1
    assert summary.invalid == 0


def test_cross_source_same_profile_is_verified_without_live_fetch():
    called = False

    def fetcher(url, timeout, max_bytes):
        nonlocal called
        called = True
        raise AssertionError("Corroborated account should not require live fetch")

    url = "https://github.com/wixxlexx"
    rows, summary = annotate_account_profile_validation(
        [
            _account(source="Sherlock", url=url),
            _account(
                source="Maigret",
                url=url,
                metadata={"registration_confirmed": True},
            ),
        ],
        fetcher=fetcher,
    )

    assert called is False
    assert all(row["accountVerificationStatus"] == "verified" for row in rows)
    assert summary.corroborated_without_fetch == 1


def test_live_check_budget_retains_unchecked_account_as_reported():
    called_urls: list[str] = []

    def fetcher(url, timeout, max_bytes):
        del timeout, max_bytes
        called_urls.append(url)
        return ProfileFetchResult(
            status_code=200,
            final_url=url,
            body="<h1>wixxlexx</h1>",
        )

    rows, summary = annotate_account_profile_validation(
        [
            _account(url="https://one.example/users/wixxlexx"),
            _account(url="https://two.example/users/wixxlexx"),
        ],
        fetcher=fetcher,
        max_live_checks=1,
    )

    statuses = {row["accountVerificationStatus"] for row in rows}
    assert statuses == {"verified", "reported"}
    assert len(called_urls) == 1
    assert summary.live_checks == 1


def test_unverified_sherlock_claim_is_blocked_from_auto_persistence():
    gate = UnifiedFindingPersistenceGate()
    finding = SimpleNamespace(
        value="wixxlexx",
        url="https://example.test/users/wixxlexx",
        metadata={
            "provider_reported_claimed": True,
            "registration_confirmed": False,
            "requires_account_verification": True,
        },
    )

    allowed = gate(
        target_type=OsintTargetType.USERNAME,
        target_value="wixxlexx",
        goal=None,
        connector="Sherlock",
        finding=finding,
    )

    assert allowed is False


def test_sherlock_no_longer_marks_claimed_as_confirmed_by_osintxz():
    text = Path("app/osint/connectors/sherlock_connector.py").read_text(
        encoding="utf-8"
    )

    assert '"provider_reported_claimed": True' in text
    assert '"requires_account_verification": True' in text
    assert '"registration_confirmed": False' in text


def test_ui_exposes_account_verification_state():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "accountVerificationStatus" in qml
    assert "accountVerificationReason" in qml
    assert "accountVerificationHttpStatus" in qml
    assert "annotate_account_profile_validation" in worker
    assert '"accountValidationSummary"' in worker
    assert '"accountInvalid"' in worker
