from pathlib import Path

from app.application.identity_resolution import build_known_identity_profile
from app.application.investigation_result_consolidation import consolidate_result_rows


def _publication(*, detail, candidate=True, source="datacite_public"):
    return {
        "lane": "Federation",
        "source": source,
        "title": "Linus Torvalds — public record",
        "detail": detail,
        "type": "publication",
        "seed": "Linus Torvalds",
        "seedType": "person_name",
        "candidateOnly": candidate,
        "identityCandidateEligible": False,
        "identityMatchScore": 100.0,
        "identityMatchReason": "full_name_match",
        "identityMatchedName": "Linus Torvalds",
        "structuredPersonMatch": True,
        "_identitySignals": {"names": ["Linus Torvalds"]},
        "status": "Candidate",
    }


def test_full_name_plus_organization_becomes_corroborating_mention():
    row = _publication(
        detail="Creator: Linus Torvalds · Affiliation: Linux Foundation · public metadata"
    )
    result = consolidate_result_rows(
        [row],
        search_profile={"organizations": "Linux Foundation"},
    )
    assert result.rows == []
    assert result.candidate_rows == []
    assert len(result.mention_rows) == 1
    mention = result.mention_rows[0]
    assert mention["mentionLabel"] in {"Corroborating mention", "Strong mention"}
    assert "Full name" in mention["mentionSignals"]
    assert "Linux Foundation" in mention["mentionSignals"]
    assert mention["mentionScore"] >= 62


def test_full_name_only_stays_review_candidate_not_mention():
    row = _publication(detail="Creator: Linus Torvalds · public metadata")
    result = consolidate_result_rows([row], search_profile={})
    assert result.mention_rows == []
    assert len(result.candidate_rows) == 1


def test_keyword_only_content_is_not_a_mention():
    row = {
        "lane": "Federation",
        "source": "internet_archive_metadata",
        "title": "Linux history",
        "detail": "Linux and open source software",
        "type": "document",
        "seed": "Linux",
        "seedType": "keyword",
        "candidateOnly": True,
        "identityCandidateEligible": False,
        "status": "Candidate",
    }
    result = consolidate_result_rows(
        [row],
        search_profile={"keywords": "Linux", "country": "FI"},
    )
    assert result.mention_rows == []


def test_account_is_never_classified_as_mention():
    row = {
        "lane": "Federation",
        "source": "github_public_user",
        "title": "Linus Torvalds",
        "detail": "Login: torvalds · Company: Linux Foundation",
        "type": "public_account",
        "seed": "torvalds",
        "seedType": "username",
        "candidateOnly": False,
        "accountCandidateEligible": True,
        "identifiers": {"username": "torvalds"},
        "url": "https://github.com/torvalds",
        "status": "Remote",
    }
    result = consolidate_result_rows(
        [row],
        search_profile={"organizations": "Linux Foundation"},
    )
    assert result.mention_rows == []
    assert len(result.related_accounts) == 1


def test_search_qml_exposes_mentions_tab():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert 'if (tab === "mentions")' in qml
    assert "runData.mentions" in qml
    assert '{ key: "mentions", label: "Mentions" }' in qml
    assert "CORROBORATING MENTION" in qml


def test_worker_exposes_mentions_and_summary_count():
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    assert '"mentions": [' in source
    assert '"mentions": len(consolidation.mention_rows or [])' in source
