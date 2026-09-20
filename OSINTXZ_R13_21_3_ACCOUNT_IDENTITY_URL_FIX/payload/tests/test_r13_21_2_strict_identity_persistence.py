from pathlib import Path
from types import SimpleNamespace

from app.application.identity_resolution import (
    build_known_identity_profile,
    is_identity_candidate_record,
    is_account_candidate_record,
    resolve_identity_record,
)
from app.application.investigation_result_consolidation import consolidate_result_rows
from app.application.person_name_relevance import match_person_name_record
from app.application.unified_persistence_relevance import build_unified_finding_gate
from app.osint.models import OsintTargetType


def _record(display_name, record_type="researcher", *, attributes=None, metadata=None, identifiers=None):
    return SimpleNamespace(
        display_name=display_name,
        record_type=record_type,
        attributes=attributes or {},
        metadata=metadata or {},
        identifiers=identifiers or {},
    )


def _finding(value, *, category="profile", url="", metadata=None):
    return SimpleNamespace(
        value=value,
        category=category,
        url=url,
        metadata=metadata or {},
    )


def test_wrong_surname_is_rejected_even_when_upstream_echoes_query_name():
    record = _record(
        "Dr. Linus Orokpo Idoko",
        attributes={"query_name": "Linus Torvalds", "search_input": "Linus Torvalds"},
    )
    match = match_person_name_record("Linus Torvalds", record)
    assert match.accepted is False
    assert match.score == 50.0

    profile = build_known_identity_profile({"firstName": "Linus", "lastName": "Torvalds"})
    resolution, signals = resolve_identity_record(profile, record, person_query="Linus Torvalds")
    assert "Linus Torvalds" not in signals.names
    assert resolution.status == "conflicting"
    assert resolution.pivot_allowed is False


def test_publication_can_be_relevant_content_but_is_not_an_identity_candidate():
    record = _record(
        "A technical publication",
        record_type="publication",
        attributes={"creator": {"name": "Linus Torvalds"}},
    )
    assert match_person_name_record("Linus Torvalds", record).accepted is True
    assert is_identity_candidate_record(record) is False


def test_public_account_is_account_signal_not_second_person_identity():
    record = _record(
        "Linus Torvalds",
        record_type="public_user",
        attributes={"login": "torvalds", "organization": "Linux Foundation"},
    )
    assert is_identity_candidate_record(record) is False
    assert is_account_candidate_record(record) is True
    assert match_person_name_record("Linus Torvalds", record).accepted is True


def test_consolidation_separates_review_candidates_from_clean_results_and_identity():
    profile = build_known_identity_profile({"firstName": "Linus", "lastName": "Torvalds"})
    rows = [
        {
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
            "_identitySignals": {"names": ["Linus Torvalds"], "usernames": ["torvalds"]},
            "contextRelevanceStatus": "relevant",
            "contextRelevanceScore": 100.0,
            "contextRelevanceKeepClean": True,
            "contextRelevancePivotAllowed": False,
        },
        {
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
            "_identitySignals": {"names": ["Linus Torvalds"]},
            "contextRelevanceStatus": "relevant",
            "contextRelevanceScore": 90.0,
            "contextRelevanceKeepClean": True,
            "contextRelevancePivotAllowed": False,
        },
    ]
    result = consolidate_result_rows(rows, identity_profile=profile)
    assert len(result.rows) == 0  # name-only profile is still review-first
    assert len(result.candidate_rows) == 2
    identity_titles = {row["title"] for row in result.identity_rows}
    assert "Linus Torvalds" not in identity_titles
    assert "A dataset by Linus Torvalds" not in identity_titles
    assert {row["title"] for row in result.related_accounts} == {"Linus Torvalds"}


def test_username_persistence_gate_accepts_exact_profile_and_rejects_unrelated_account():
    gate = build_unified_finding_gate({})
    assert gate(
        target_type=OsintTargetType.USERNAME,
        target_value="torvalds",
        goal=None,
        connector="fixture",
        finding=_finding("https://github.com/torvalds", url="https://github.com/torvalds"),
    )
    assert not gate(
        target_type=OsintTargetType.USERNAME,
        target_value="torvalds",
        goal=None,
        connector="fixture",
        finding=_finding("https://github.com/unrelated", url="https://github.com/unrelated"),
    )


def test_exact_identifier_persistence_gate_is_strict():
    gate = build_unified_finding_gate({})
    assert gate(
        target_type=OsintTargetType.EMAIL,
        target_value="linus@example.org",
        goal=None,
        connector="fixture",
        finding=_finding("linus@example.org", category="email"),
    )
    assert not gate(
        target_type=OsintTargetType.EMAIL,
        target_value="linus@example.org",
        goal=None,
        connector="fixture",
        finding=_finding("other@example.org", category="email"),
    )
    assert gate(
        target_type=OsintTargetType.DOMAIN,
        target_value="example.org",
        goal=None,
        connector="fixture",
        finding=_finding("sub.example.org", category="domain"),
    )


def test_worker_installs_gate_and_exposes_candidates_tab_contract():
    worker = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert "build_unified_finding_gate(self.profile)" in worker
    assert '"candidates": [' in worker
    assert '{ key: "candidates", label: "Candidates" }' in qml
    assert "runData.candidates" in qml


def test_finding_persistence_service_contains_optional_pre_persistence_gate_after_install():
    path = Path("app/osint/finding_persistence.py")
    if not path.exists():
        # Payload-only unit runs do not include the large pre-existing core file;
        # the installer patches it in the real project before executing tests.
        return
    source = path.read_text(encoding="utf-8")
    assert "R13.21.2 pre-persistence relevance gate" in source
    assert "self.finding_gate" in source
    assert "_passes_finding_gate" in source
