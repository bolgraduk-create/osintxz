from pathlib import Path

from app.application.contextual_relevance import assess_result_row
from app.application.investigation_result_consolidation import consolidate_result_rows
from app.osint.connectors.sherlock_connector import SherlockConnector
from app.osint.connectors.maigret_connector import MaigretConnector
from app.osint.connectors.user_scanner_connector import UserScannerConnector
from app.osint.models import OsintTargetType


def _account_row(username: str, **extra):
    row = {
        "lane": "Classic OSINT",
        "source": "SocialScan",
        "title": username,
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": "",
        "seed": username,
        "seedType": "username",
        "identifiers": {"username": username},
        "findingMetadata": {"registration_confirmed": True, "service": "instagram"},
        "candidateOnly": False,
        "sensitive": False,
        "depth": 0,
    }
    row.update(extra)
    return row


def test_exact_account_without_url_is_relevant_and_clean():
    row = _account_row("texnobreath")
    relevance = assess_result_row(row)
    assert relevance.keep_clean
    assert relevance.pivot_allowed
    result = consolidate_result_rows([row], seeds=[{"kind": "username", "value": "texnobreath"}])
    assert len(result.rows) == 1
    assert result.rows[0]["title"] == "texnobreath"


def test_exact_account_negative_metadata_is_not_promoted():
    row = _account_row(
        "texnobreath",
        identifiers={},
        findingMetadata={"available": True, "service": "fixture"},
    )
    relevance = assess_result_row(row)
    # The exact identifier is deliberately absent; an explicit "available"
    # result must not be upgraded merely because the title echoes the seed.
    assert not relevance.keep_clean


def test_unrelated_historical_url_stays_suppressed():
    row = {
        "lane": "Classic OSINT",
        "source": "GAU",
        "title": "https://gitlab.com/adamstoolkit",
        "detail": "Historical Url",
        "type": "historical_url",
        "url": "https://gitlab.com/adamstoolkit",
        "seed": "texnobreath",
        "seedType": "username",
        "candidateOnly": False,
        "depth": 1,
    }
    relevance = assess_result_row(row)
    assert not relevance.keep_clean
    result = consolidate_result_rows([row], seeds=[{"kind": "username", "value": "texnobreath"}])
    assert result.rows == []


def test_sherlock_recovers_claimed_owner_url_from_partial_stdout():
    findings = SherlockConnector._stdout_findings(
        "[+] GitHub: https://github.com/texnobreath\n"
        "[+] Other: https://gitlab.com/adamstoolkit\n",
        "texnobreath",
    )
    assert len(findings) == 1
    assert findings[0].url == "https://github.com/texnobreath"
    assert findings[0].value == "texnobreath"


def test_sherlock_uses_local_database_and_larger_bounded_budget():
    text = Path("app/osint/connectors/sherlock_connector.py").read_text(encoding="utf-8")
    assert '"--local"' in text
    assert SherlockConnector._process_budget(20) >= 60
    assert SherlockConnector._process_budget(20) <= 80


def test_maigret_restores_broader_fast_pass():
    text = Path("app/osint/connectors/maigret_connector.py").read_text(encoding="utf-8")
    assert '"--top-sites", "300"' in text
    assert "partial_stdout_recovery" in text
    assert MaigretConnector._process_budget(20) >= 70


def test_user_scanner_username_is_split_into_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(UserScannerConnector, "module_available", classmethod(lambda cls: True))
    command = UserScannerConnector._build_command(
        target_type=OsintTargetType.USERNAME,
        value="texnobreath",
        output=tmp_path / "x.json",
        category="social",
    )
    assert "-u" in command
    assert "-c" in command and "social" in command
    assert "-f" in command and "json" in command
    assert UserScannerConnector.USERNAME_CATEGORIES[0] == "social"


def test_worker_preserves_classic_finding_metadata_and_username_identifier():
    text = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    assert '"findingMetadata": finding_metadata' in text
    assert 'identifiers["username"] = target' in text
    assert "USERNAME_CLASSIC_TIMEOUT = 20" in text
