from __future__ import annotations

from pathlib import Path

from app.application.search_quality_engine import (
    annotate_search_quality_rows,
    assess_search_quality_row,
    quality_trace_rows,
)


def _username_account(**overrides):
    row = {
        "lane": "Classic OSINT",
        "source": "Sherlock",
        "title": "texnobreath",
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": "https://github.com/texnobreath",
        "seed": "texnobreath",
        "seedType": "username",
        "identifiers": {"username": "texnobreath"},
        "findingMetadata": {
            "exists": "Claimed",
            "registration_confirmed": True,
        },
        "confidence": 0.97,
        "reliability": 0.93,
        "candidateOnly": False,
        "depth": 0,
    }
    row.update(overrides)
    return row


def test_exact_username_account_is_shadow_strong_and_explorable():
    assessment = assess_search_quality_row(_username_account())

    assert assessment.tier == "strong"
    assert assessment.score >= 85
    assert assessment.would_show is True
    assert assessment.would_explore is True
    assert assessment.would_persist is True
    assert assessment.hard_reject_reason == ""


def test_explicit_provider_absence_overrides_exact_username_in_shadow_only():
    row = _username_account(
        findingMetadata={
            "exists": False,
            "registration_confirmed": False,
        }
    )

    assessment = assess_search_quality_row(row)

    assert assessment.tier == "noise"
    assert assessment.hard_reject_reason
    assert "absent" in assessment.hard_reject_reason.casefold()
    assert assessment.would_show is False
    assert assessment.would_explore is False
    assert assessment.would_persist is False
    # The point of shadow mode is to expose disagreements before changing
    # current behaviour.  Contextual relevance still sees the exact username.
    assert assessment.legacy_visible is True
    assert assessment.disagreement is True


def test_weak_unproven_username_stays_noise_without_hard_reject():
    row = {
        "lane": "Open-Web",
        "source": "example",
        "title": "Unrelated project page",
        "detail": "No account proof",
        "type": "document",
        "url": "https://example.test/project",
        "seed": "texnobreath",
        "seedType": "username",
        "identifiers": {},
        "candidateOnly": False,
        "depth": 0,
    }

    assessment = assess_search_quality_row(row)

    assert assessment.tier == "noise"
    assert assessment.hard_reject_reason == ""
    assert assessment.would_explore is False
    assert assessment.would_persist is False


def test_annotation_preserves_original_rows_and_adds_explainable_fields():
    original = _username_account()
    annotated, summary = annotate_search_quality_rows([original])

    assert "qualityTier" not in original
    assert annotated[0]["qualityTier"] == "strong"
    assert annotated[0]["qualityObservationId"] == "obs-0001"
    assert annotated[0]["qualityPositiveSignals"]
    assert "qualitySummary" in annotated[0]
    assert summary.total == 1
    assert summary.strong == 1


def test_quality_trace_sorts_disagreements_before_higher_non_disagreement():
    normal, _ = annotate_search_quality_rows([_username_account()])
    conflicting, _ = annotate_search_quality_rows(
        [
            _username_account(
                findingMetadata={
                    "exists": False,
                    "registration_confirmed": False,
                }
            )
        ]
    )

    trace = quality_trace_rows([normal[0], conflicting[0]])

    assert trace[0]["qualityDisagreement"] is True
    assert trace[0]["qualityTier"] == "noise"


def test_worker_exposes_quality_trace_without_replacing_existing_pipeline():
    text = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")

    assert "annotate_search_quality_rows" in text
    assert '"qualityTrace": quality_trace' in text
    assert '"qualitySummary": quality_summary.to_dict()' in text
    assert "consolidate_result_rows(" in text
    assert "build_unified_finding_gate" in text


def test_search_qml_exposes_quality_tab():
    text = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )

    assert '{ key: "quality", label: "Quality" }' in text
    assert "runData.qualityTrace" in text
    assert "qualityDisagreement" in text
    assert "qualityPivotScore" in text
    assert "qualityPersistenceScore" in text
