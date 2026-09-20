from pathlib import Path

from app.application.investigation_result_consolidation import consolidate_result_rows


def test_cross_source_exact_email_collapses_and_becomes_corroborated():
    rows = [
        {"lane": "Classic OSINT", "source": "a", "title": "Alice@Example.com", "type": "email", "status": "Finding", "depth": 0},
        {"lane": "Open-Web", "source": "b", "title": "alice@example.com", "type": "email_address", "status": "Extracted", "depth": 1},
        {"lane": "Federation", "source": "c", "title": "alice@example.com", "type": "email", "status": "Remote", "depth": 0},
    ]
    result = consolidate_result_rows(rows)
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["corroborationCount"] == 3
    assert row["duplicatesMerged"] == 2
    assert row["status"] == "Corroborated"
    assert row["source"] == "3 sources"
    assert result.duplicates_collapsed == 2


def test_tracking_only_url_variants_collapse():
    rows = [
        {"lane": "Open-Web", "source": "a", "title": "Page", "type": "document", "url": "https://Example.com/a/?utm_source=x&b=2", "depth": 0},
        {"lane": "Open-Web", "source": "b", "title": "Same page", "type": "document", "url": "https://example.com/a?b=2#fragment", "depth": 0},
    ]
    result = consolidate_result_rows(rows)
    assert len(result.rows) == 1
    assert result.rows[0]["url"] == "https://example.com/a?b=2"
    assert result.rows[0]["corroborationCount"] == 2


def test_exact_identifier_merges_registry_title_variants():
    rows = [
        {"lane": "Registry", "source": "one", "title": "ACME LTD", "type": "organization", "identifiers": {"LEI": "5493001KJTIIGC8Y1R12"}},
        {"lane": "Federation", "source": "two", "title": "Acme Limited", "type": "legal_entity", "identifiers": {"lei": "5493001KJTIIGC8Y1R12"}},
    ]
    result = consolidate_result_rows(rows)
    assert len(result.rows) == 1
    assert result.rows[0]["corroborationCount"] == 2


def test_person_names_are_not_fuzzy_merged():
    rows = [
        {"lane": "Federation", "source": "a", "title": "John Smith", "type": "person", "candidateOnly": True},
        {"lane": "Federation", "source": "b", "title": "John A. Smith", "type": "person", "candidateOnly": True},
    ]
    result = consolidate_result_rows(rows)
    assert len(result.rows) == 0
    assert len(result.candidate_rows) == 2


def test_obvious_seed_echo_without_provenance_is_suppressed():
    rows = [
        {"lane": "Classic OSINT", "source": "echo", "title": "example.com", "detail": "Domain", "type": "domain", "seed": "example.com", "seedType": "domain", "depth": 0},
        {"lane": "Classic OSINT", "source": "useful", "title": "sub.example.com", "detail": "Domain", "type": "domain", "seed": "example.com", "seedType": "domain", "depth": 0},
    ]
    result = consolidate_result_rows(rows, seeds=[{"kind": "domain", "value": "example.com"}])
    assert [row["title"] for row in result.rows] == ["sub.example.com"]
    assert result.low_value_suppressed == 1


def test_rank_prefers_exact_corroborated_over_candidate_document():
    rows = [
        {"lane": "Open-Web", "source": "web", "title": "Some article", "type": "document", "url": "https://example.org/article", "candidateOnly": True, "depth": 2},
        {"lane": "Classic OSINT", "source": "a", "title": "user@example.org", "type": "email", "depth": 0},
        {"lane": "Federation", "source": "b", "title": "user@example.org", "type": "email", "depth": 0},
    ]
    result = consolidate_result_rows(rows)
    assert result.rows[0]["title"].casefold() == "user@example.org"
    assert result.rows[0]["quality"] == "high"


def test_worker_and_qml_wire_clean_and_raw_views():
    worker = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert "consolidate_result_rows" in worker
    assert '"rawResults": raw_results[:500]' in worker
    assert '"duplicatesCollapsed"' in worker
    assert 'property string resultViewMode: "clean"' in qml
    assert '{ key: "clean", label: "Clean" }' in qml
    assert '{ key: "raw", label: "Raw" }' in qml
