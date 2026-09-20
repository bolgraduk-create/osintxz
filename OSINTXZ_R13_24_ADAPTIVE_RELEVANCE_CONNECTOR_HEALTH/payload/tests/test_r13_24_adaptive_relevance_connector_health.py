from __future__ import annotations

from pathlib import Path

from app.application.adaptive_relevance import classify_suppressed_row
from app.application.connector_health import annotate_provider_health, classify_provider_health
from app.osint.connectors.sherlock_connector import SherlockConnector
from app.osint.connectors.maigret_connector import MaigretConnector
from app.osint.connectors.user_scanner_connector import UserScannerConnector
from app.osint.models import OsintTargetType
from app.intelligence_sources.adapters.wikidata_search import WikidataEntitySearchAdapter


def test_exact_username_is_not_resurrected_as_possible():
    item = classify_suppressed_row({
        "seedType": "username",
        "seed": "torvalds",
        "title": "https://gitlab.com/otheruser/project",
        "contextRelevanceStatus": "low_relevance",
        "contextRelevanceScore": 8,
        "contextMatchedTerms": ["Linux", "Git"],
    })
    assert item.tier == "suppressed"


def test_keyword_and_multi_context_can_be_visible_as_possible():
    keyword = classify_suppressed_row({
        "seedType": "keyword", "seed": "kernel", "title": "Linux kernel history",
        "contextRelevanceStatus": "candidate", "contextRelevanceScore": 45,
    })
    assert keyword.visible_as_possible
    contextual = classify_suppressed_row({
        "seedType": "organization", "seed": "Linux Foundation", "title": "Open source conference",
        "contextRelevanceStatus": "low_relevance", "contextRelevanceScore": 20,
        "contextMatchedTerms": ["Linux", "Portland"],
    })
    assert contextual.visible_as_possible


def test_health_classifies_timeout_missing_and_403():
    assert classify_provider_health({"status": "failed", "detail": "Process timeout."})[0] == "timeout"
    assert classify_provider_health({"status": "not_available", "detail": "not installed"})[0] == "not_installed"
    assert classify_provider_health({"status": "failed", "detail": "HTTP 403."})[0] == "auth_or_policy"
    rows, summary = annotate_provider_health([
        {"status": "success", "source": "x"},
        {"status": "failed", "source": "y", "detail": "Process timeout."},
    ])
    assert rows[0]["healthLabel"] == "READY"
    assert summary["ready"] == 1 and summary["timeout"] == 1 and summary["issues"] == 1


def test_sherlock_fast_pass_uses_current_cli_flags():
    assert SherlockConnector._site_timeout(15) <= 7
    source = Path(SherlockConnector.__module__.replace(".", "/") + ".py")
    # Source marker test is deliberately path-independent in installed project.
    text = Path("app/osint/connectors/sherlock_connector.py").read_text(encoding="utf-8")
    assert '"--timeout"' in text
    assert '"--no-txt"' not in text
    assert "partial findings retained" in text.lower()


def test_maigret_fast_pass_is_bounded_and_non_recursive():
    text = Path("app/osint/connectors/maigret_connector.py").read_text(encoding="utf-8")
    for marker in ('"--top-sites", "140"', '"--no-recursion"', '"--no-extracting"', '"--retries", "0"'):
        assert marker in text
    assert MaigretConnector._process_budget(15) <= 90


def test_user_scanner_command_avoids_version_specific_timeout_flags(tmp_path):
    cmd = UserScannerConnector._build_command(
        target_type=OsintTargetType.USERNAME,
        value="example",
        output=tmp_path / "x.json",
    )
    assert "-u" in cmd and "-f" in cmd and "json" in cmd
    assert "-t" not in cmd
    assert "--no-nsfw" not in cmd


def test_wikidata_client_uses_descriptive_contactable_user_agent():
    adapter = WikidataEntitySearchAdapter()
    assert "github.com/bolgraduk-create/osintxz" in adapter.client.user_agent
    assert adapter.client.extra_headers.get("Api-User-Agent") == adapter.client.user_agent


def test_search_ui_exposes_possible_and_provider_health():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert '{ key: "possible", label: "Possible" }' in qml
    assert "runData.possibleResults" in qml
    assert "healthLabel" in qml
    worker = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    assert '"possibleResults"' in worker
    assert '"healthSummary"' in worker
