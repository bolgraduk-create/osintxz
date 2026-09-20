from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.contextual_relevance import (
    assess_record_against_seed,
    assess_result_row,
    context_boost,
    context_terms_from_profile,
)
from app.application.investigation_result_consolidation import consolidate_result_rows


def _seed(kind: str, value: str):
    return SimpleNamespace(kind=SimpleNamespace(value=kind), value=value)


def _record(name: str, **attrs):
    return SimpleNamespace(
        display_name=name,
        record_id=attrs.pop("record_id", name),
        record_type=attrs.pop("record_type", "organization"),
        country=attrs.pop("country", None),
        identifiers=attrs.pop("identifiers", {}),
        attributes=attrs.pop("attributes", {}),
        metadata=attrs.pop("metadata", {}),
        **attrs,
    )


def test_organization_seed_rejects_shared_generic_word_only() -> None:
    seed = _seed("organization", "Linux Foundation")
    wrong = assess_record_against_seed(seed, _record("Alfred Kordelin Foundation"))
    right = assess_record_against_seed(seed, _record("The Linux Foundation"))

    assert wrong.status == "low_relevance"
    assert wrong.keep_clean is False
    assert wrong.pivot_allowed is False
    assert right.status == "relevant"
    assert right.keep_clean is True
    assert right.pivot_allowed is True


def test_upstream_explicit_non_match_is_suppressed() -> None:
    seed = _seed("organization", "Linux Foundation")
    record = _record(
        "ASIARTA FOUNDATION",
        attributes={"match": False, "candidate_only": True, "score": 22.2},
    )
    assessment = assess_record_against_seed(seed, record)
    assert assessment.keep_clean is False
    assert assessment.pivot_allowed is False


def test_exact_username_must_be_present_for_federation_record() -> None:
    seed = _seed("username", "torvalds")
    right = _record(
        "torvalds",
        record_type="profile",
        identifiers={"username": "torvalds"},
    )
    wrong = _record(
        "another-user",
        record_type="profile",
        identifiers={"username": "another-user"},
    )
    assert assess_record_against_seed(seed, right).pivot_allowed is True
    assert assess_record_against_seed(seed, wrong).keep_clean is False


def test_keyword_is_context_only_in_clean_view() -> None:
    row = {
        "lane": "Federation",
        "source": "archive",
        "title": "Linux kernel article",
        "detail": "Linux appears here",
        "type": "document",
        "seed": "Linux",
        "seedType": "keyword",
        "candidateOnly": True,
    }
    assessment = assess_result_row(row)
    assert assessment.status == "candidate"
    assert assessment.keep_clean is False
    assert assessment.pivot_allowed is False


def test_context_terms_boost_but_do_not_create_relevance() -> None:
    terms = context_terms_from_profile(
        {"keywords": "Linux\nGit", "organizations": "Linux Foundation", "country": "FI"}
    )
    boost, matched = context_boost(
        {"title": "Linus Torvalds", "detail": "Linux and Git", "meta": "FI"}, terms
    )
    assert boost > 0
    assert "Linux" in matched


def test_consolidation_suppresses_irrelevant_organization_candidate() -> None:
    rows = [
        {
            "lane": "Federation",
            "source": "icij_offshore_leaks",
            "title": "ASIARTA FOUNDATION",
            "detail": "Score: 22.2 · Match: False · Candidate Only: True",
            "type": "organization",
            "seed": "Linux Foundation",
            "seedType": "organization",
            "candidateOnly": True,
        },
        {
            "lane": "Federation",
            "source": "wikidata_search",
            "title": "Linux Foundation",
            "detail": "Organization",
            "type": "organization",
            "seed": "Linux Foundation",
            "seedType": "organization",
            "candidateOnly": True,
        },
    ]
    result = consolidate_result_rows(
        rows,
        seeds=[{"kind": "organization", "value": "Linux Foundation"}],
        search_profile={"organizations": "Linux Foundation", "keywords": "Linux\nGit"},
    )
    assert result.rows == []
    assert len(result.candidate_rows) == 1
    assert result.candidate_rows[0]["title"] == "Linux Foundation"
    assert result.low_value_suppressed >= 1


def test_qml_has_identity_tab_and_adaptive_rows() -> None:
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert '{ key: "identity", label: "Identity" }' in qml
    assert 'title: "Identity Leads"' in qml
    assert "needsExtraLine" in qml
    assert "maximumLineCount: row.needsExtraLine ? 2 : 1" in qml
    assert "rightColumnWidth" in qml


def test_planner_treats_keywords_as_context_and_organization_routes_are_narrow() -> None:
    source = Path("app/application/unified_investigation_search.py").read_text(encoding="utf-8")
    assert "Keywords are context by default" in source
    assert "if seed.kind is not UnifiedSeedKind.KEYWORD" in source
    capability_section = source.split("\n_CAPABILITY_PRIORITIES:", 1)[1]
    org_block = capability_section.split("UnifiedSeedKind.ORGANIZATION: (", 1)[1].split("),", 1)[0]
    assert '"organization"' in org_block
    assert '"archive_search"' not in org_block
    assert '"keyword"' not in org_block


def test_worker_groups_repeated_errors_and_passes_profile_to_consolidation() -> None:
    source = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    assert "errors = self._group_error_rows(errors)" in source
    assert 'item["attempts"]' in source
    assert "search_profile=self.profile" in source
    assert "assess_record_against_seed(seed, record)" in source
