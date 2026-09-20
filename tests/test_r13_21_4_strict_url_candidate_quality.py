from pathlib import Path

from app.application.contextual_relevance import assess_result_row
from app.application.identity_resolution import build_known_identity_profile
from app.application.investigation_result_consolidation import consolidate_result_rows


def _row(*, title, url, seed, seed_type, lane="Classic OSINT", source="GAU", candidate=False, **extra):
    row = {
        "lane": lane,
        "source": source,
        "title": title,
        "detail": "Historical Url",
        "type": "historical_url",
        "status": "Finding",
        "url": url,
        "seed": seed,
        "seedType": seed_type,
        "candidateOnly": candidate,
        "sensitive": False,
        "depth": 1,
    }
    row.update(extra)
    return row


def test_url_seed_accepts_same_profile_scope_and_rejects_other_account():
    seed = "https://gitlab.com/torvalds"
    exact = assess_result_row(_row(
        title=seed,
        url=seed,
        seed=seed,
        seed_type="url",
    ))
    child = assess_result_row(_row(
        title="https://gitlab.com/torvalds/linux/-/releases",
        url="https://gitlab.com/torvalds/linux/-/releases",
        seed=seed,
        seed_type="url",
    ))
    unrelated = assess_result_row(_row(
        title="https://gitlab.com/adamstoolkit",
        url="https://gitlab.com/adamstoolkit",
        seed=seed,
        seed_type="url",
    ))
    assert exact.keep_clean and exact.pivot_allowed
    assert child.keep_clean and child.pivot_allowed
    assert unrelated.keep_clean is False
    assert unrelated.pivot_allowed is False
    assert "outside" in unrelated.summary.casefold()


def test_url_seed_no_longer_uses_exact_target_provider_fallback():
    assessment = assess_result_row(_row(
        title="https://gitlab.com/cip-project/cip-kernel/cip-kernel-sec",
        url="https://gitlab.com/cip-project/cip-kernel/cip-kernel-sec",
        seed="https://gitlab.com/torvalds",
        seed_type="url",
        lane="Classic OSINT",
        source="GAU",
    ))
    assert assessment.status == "low_relevance"
    assert assessment.score < 20
    assert assessment.keep_clean is False


def test_consolidation_suppresses_unrelated_second_wave_url_from_clean():
    rows = [
        _row(
            title="https://gitlab.com/torvalds/linux",
            url="https://gitlab.com/torvalds/linux",
            seed="https://gitlab.com/torvalds",
            seed_type="url",
        ),
        _row(
            title="https://gitlab.com/adamstoolkit",
            url="https://gitlab.com/adamstoolkit",
            seed="https://gitlab.com/torvalds",
            seed_type="url",
        ),
    ]
    result = consolidate_result_rows(rows)
    assert [row["url"] for row in result.rows] == ["https://gitlab.com/torvalds/linux"]
    assert result.low_value_suppressed >= 1


def test_identity_review_rows_are_not_duplicated_in_candidates():
    profile = build_known_identity_profile({"firstName": "Linus", "lastName": "Torvalds"})
    rows = [{
        "lane": "Federation",
        "source": "semantic_scholar",
        "title": "Linus Torvalds",
        "detail": "Paper Count: 12",
        "type": "researcher",
        "seed": "Linus Torvalds",
        "seedType": "person_name",
        "candidateOnly": True,
        "identityCandidateEligible": True,
        "identityMatchScore": 100.0,
        "identityMatchReason": "full_name_match",
        "identityMatchedName": "Linus Torvalds",
        "_identitySignals": {"names": ["Linus Torvalds"]},
    }]
    result = consolidate_result_rows(rows, identity_profile=profile)
    assert len(result.identity_rows) == 1
    assert result.identity_rows[0]["identityStatus"] == "insufficient"
    assert result.candidate_rows == []


def test_person_content_candidate_requires_structured_matched_name_marker():
    weak = {
        "lane": "Federation",
        "source": "internet_archive_metadata",
        "title": "HD Wallpaper Linux The World is Open Source",
        "detail": "Candidate Only: True",
        "type": "document",
        "seed": "Linus Torvalds",
        "seedType": "person_name",
        "candidateOnly": True,
        "identityCandidateEligible": False,
        "identityMatchScore": 100.0,
        "identityMatchReason": "full_name_match",
        # Deliberately no identityMatchedName: the source did not prove a
        # structured author/creator/person association.
    }
    result = consolidate_result_rows([weak])
    assert result.rows == []
    assert result.candidate_rows == []


def test_structured_person_content_candidate_remains_reviewable():
    relevant = {
        "lane": "Federation",
        "source": "datacite_public",
        "title": "A dataset by Linus Torvalds",
        "detail": "Creator: Linus Torvalds",
        "type": "publication",
        "seed": "Linus Torvalds",
        "seedType": "person_name",
        "candidateOnly": True,
        "identityCandidateEligible": False,
        "identityMatchScore": 100.0,
        "identityMatchReason": "full_name_match",
        "identityMatchedName": "Linus Torvalds",
    }
    result = consolidate_result_rows([relevant])
    assert result.rows == []
    assert len(result.candidate_rows) == 1
    assert result.candidate_rows[0]["title"] == "A dataset by Linus Torvalds"


def test_qml_identity_metric_reports_review_counts_instead_of_ambiguous_zero():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert 'title: "Identity Leads"' in qml
    assert 'root.summary.identityCandidates' in qml
    assert 'root.summary.identityInsufficient' in qml
    assert '" supported · "' in qml
    assert '" review · "' in qml


def test_username_persistence_owner_position_is_strict():
    from app.application.unified_persistence_relevance import build_unified_finding_gate
    from app.osint.models import OsintTargetType

    class Finding:
        def __init__(self, value, url=""):
            self.value = value
            self.url = url
            self.metadata = {}

    gate = build_unified_finding_gate({})
    assert gate(
        target_type=OsintTargetType.USERNAME,
        target_value="torvalds",
        goal=None,
        connector="fixture",
        finding=Finding("https://github.com/torvalds/linux", "https://github.com/torvalds/linux"),
    )
    assert not gate(
        target_type=OsintTargetType.USERNAME,
        target_value="torvalds",
        goal=None,
        connector="fixture",
        finding=Finding(
            "https://example.org/project/issues/torvalds",
            "https://example.org/project/issues/torvalds",
        ),
    )
