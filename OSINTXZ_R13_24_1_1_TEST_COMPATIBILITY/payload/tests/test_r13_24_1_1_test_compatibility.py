from pathlib import Path
import re


def test_r13_24_1_maigret_300_is_accepted_by_regression_contract():
    text = Path("app/osint/connectors/maigret_connector.py").read_text(encoding="utf-8")
    match = re.search(r'"--top-sites"\s*,\s*"(\d+)"', text)
    assert match is not None
    assert int(match.group(1)) == 300
    assert '"--no-recursion"' in text
    assert '"--no-extracting"' in text
    assert '"--retries", "0"' in text


def test_r13_24_regression_no_longer_hardcodes_140():
    text = Path("tests/test_r13_24_adaptive_relevance_connector_health.py").read_text(encoding="utf-8")
    assert '"--top-sites", "140"' not in text
    assert "top_sites <= 500" in text
