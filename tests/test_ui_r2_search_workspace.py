from __future__ import annotations

from pathlib import Path


SEARCH_QML = Path("app/interface/desktop/qml/pages/Search.qml")


def _qml() -> str:
    return SEARCH_QML.read_text(encoding="utf-8")


def test_ui_r2_exposes_three_primary_result_sections():
    qml = _qml()

    for expected in (
        '{ key: "results", label: "Results" }',
        '{ key: "review", label: "Review" }',
        '{ key: "activity", label: "Activity" }',
    ):
        assert expected in qml

    assert "function resultSectionForTab(tab)" in qml
    assert "function sectionDefaultTab(section)" in qml
    assert "function sectionTabs(section)" in qml
    assert "function sectionCount(section)" in qml


def test_ui_r2_preserves_all_existing_result_modes_as_subfilters():
    qml = _qml()

    for key, label in (
        ("results", "Results"),
        ("accounts", "Accounts"),
        ("mentions", "Mentions"),
        ("possible", "Possible"),
        ("identity", "Identity"),
        ("candidates", "Candidates"),
        ("providers", "Providers"),
        ("pivots", "Pivots"),
        ("quality", "Quality"),
        ("exploration", "Explore"),
        ("schedule", "Schedule"),
        ("errors", "Errors"),
    ):
        assert f'{{ key: "{key}", label: "{label}" }}' in qml


def test_ui_r2_keeps_clean_raw_result_switch():
    qml = _qml()

    assert '{ key: "clean", label: "Clean" }' in qml
    assert '{ key: "raw", label: "Raw" }' in qml
    assert 'root.activeTab === "results" && root.runData.hasRun' in qml


def test_ui_r2_collapses_advanced_identifiers_without_dropping_payload_fields():
    qml = _qml()

    assert "property bool advancedFieldsOpen: false" in qml
    assert 'text: "ADDITIONAL IDENTIFIERS"' in qml
    assert "visible: root.advancedFieldsOpen" in qml

    for field_id in (
        "country", "region", "city", "postalCode", "address",
        "organizations", "registrationIds", "vatIds", "leis",
        "caseNumbers", "orcids", "domains", "urls", "ips", "asns",
        "hashes", "cves", "dois", "npis", "cryptoAddresses", "keywords",
    ):
        assert qml.count(f"id: {field_id}") == 1
        assert f"{field_id}:" in qml


def test_ui_r2_search_policy_is_progressively_disclosed_and_contract_is_preserved():
    qml = _qml()

    assert "property bool searchPolicyOpen: false" in qml
    assert 'text: "SEARCH POLICY"' in qml
    assert "visible: root.searchPolicyOpen" in qml

    for field_id in (
        "classicCheck", "webCheck", "federationCheck",
        "registryCheck", "pivotCheck", "sensitiveCheck",
    ):
        assert qml.count(f"id: {field_id}") == 1

    for option_key, control_id in (
        ("classic", "classicCheck"),
        ("openWeb", "webCheck"),
        ("federation", "federationCheck"),
        ("registry", "registryCheck"),
        ("followPivots", "pivotCheck"),
        ("includeSensitiveNameRoutes", "sensitiveCheck"),
    ):
        assert f"{option_key}: {control_id}.checked" in qml


def test_ui_r2_replaces_large_search_metrics_with_compact_metrics():
    qml = _qml()

    assert "component CompactMetric: Rectangle" in qml
    assert 'title: "Known Seeds"' in qml
    assert 'title: "Results"' in qml
    assert 'title: "Identity Leads"' in qml
    assert 'title: "New Pivots"' in qml


def test_ui_r2_keeps_target_person_attribution_and_run_contract():
    qml = _qml()

    assert 'id: targetPersonBox' in qml
    assert 'text: "+ New Person"' in qml
    assert "root.selectedTargetPersonId.length > 0" in qml
    assert "investigationSearchBridge.search(" in qml
    assert "root.profilePayload()" in qml
    assert "root.optionPayload()" in qml
    assert "root.selectedTargetPersonId" in qml
