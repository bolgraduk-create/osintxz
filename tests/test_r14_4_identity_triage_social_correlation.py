from __future__ import annotations

from app.application.identity_triage import build_identity_triage
from app.application.social_content_correlation import (
    correlate_social_content,
    normalize_social_content,
)


def test_identity_triage_preserves_human_authority_and_machine_signals():
    rows = [
        {
            "type": "account",
            "title": "@alpha",
            "service": "GitHub",
            "url": "https://github.com/alpha",
            "identifiers": {"username": "alpha"},
            "accountVerificationStatus": "verified",
            "confidence": 0.72,
            "reviewStatus": "confirmed",
        },
        {
            "type": "account",
            "title": "@alpha",
            "service": "Reddit",
            "url": "https://reddit.com/user/alpha",
            "identifiers": {"username": "alpha"},
            "accountVerificationStatus": "likely",
            "confidence": 0.67,
        },
        {
            "type": "account",
            "title": "@wrong",
            "service": "Example",
            "url": "https://example.test/wrong",
            "identifiers": {"username": "wrong"},
            "accountVerificationStatus": "verified",
            "confidence": 0.92,
            "reviewStatus": "rejected",
        },
    ]

    triage, clusters, summary = build_identity_triage(rows)

    by_title = {row["title"]: row for row in triage}
    assert by_title["@wrong"]["triageStatus"] == "rejected"
    assert by_title["@wrong"]["triageAuthoritative"] is True
    assert by_title["@wrong"]["triageScore"] <= 35.0

    alpha_rows = [row for row in triage if row["title"] == "@alpha"]
    assert {row["triageStatus"] for row in alpha_rows} == {
        "confirmed",
        "needs_review",
    }
    assert summary.total == 3
    assert summary.confirmed == 1
    assert summary.rejected == 1
    assert summary.needs_review == 1

    assert len(clusters) == 1
    assert clusters[0]["clusterValue"] == "alpha"
    assert set(clusters[0]["platforms"]) == {"GitHub", "Reddit"}
    assert "not proof of ownership" in clusters[0]["correlationSummary"]


def test_machine_verified_without_analyst_decision_is_not_authoritative():
    triage, _clusters, _summary = build_identity_triage(
        [
            {
                "type": "account",
                "title": "@alpha",
                "accountVerificationStatus": "verified",
                "confidence": 0.91,
            }
        ]
    )
    assert triage[0]["triageStatus"] == "confirmed"
    assert triage[0]["triageAuthoritative"] is False


def test_social_content_normalization_and_context_correlation():
    raw = [
        {
            "type": "post",
            "platform": "Reddit",
            "author": "alpha",
            "text": "Flying to Thailand tomorrow #bangkok",
            "url": "https://reddit.test/a",
            "timestamp": "2026-08-10T10:00:00+00:00",
        },
        {
            "type": "comment",
            "platform": "GitHub",
            "author": "alpha_dev",
            "text": "Bangkok trip was great #bangkok",
            "url": "https://github.test/b",
            "timestamp": "2026-08-12T10:00:00+00:00",
        },
    ]

    items = normalize_social_content(raw)
    assert len(items) == 2
    assert items[0]["contentType"] == "post"
    assert "#bangkok" in items[0]["entities"]

    correlations = correlate_social_content(items)
    assert correlations
    assert "#bangkok" in correlations[0]["sharedSignals"]
    assert correlations[0]["correlationScore"] >= 36.0
    assert "supporting evidence only" in correlations[0]["correlationSummary"]


def test_search_workspace_exposes_triage_and_correlation_tabs():
    from pathlib import Path

    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    for token in (
        '{ key: "triage", label: "Triage" }',
        '{ key: "correlation", label: "Correlation" }',
        "runData.triageRows",
        "runData.identityCorrelations",
        "triageStatus",
        "correlationSummary",
    ):
        assert token in qml

    for token in (
        "build_identity_triage",
        '"triageRows":',
        '"identityCorrelations":',
        '"triageSummary":',
    ):
        assert token in worker
