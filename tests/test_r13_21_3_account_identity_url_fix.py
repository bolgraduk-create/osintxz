from pathlib import Path
from types import SimpleNamespace

from app.application.contextual_relevance import assess_record_against_seed, assess_result_row
from app.application.identity_resolution import (
    build_known_identity_profile,
    is_account_candidate_record,
    is_account_candidate_type,
    is_identity_candidate_record,
    is_identity_candidate_type,
)
from app.application.investigation_result_consolidation import consolidate_result_rows
import pytest


def _seed(kind: str, value: str):
    return SimpleNamespace(kind=SimpleNamespace(value=kind), value=value)


def test_accounts_are_not_person_identity_candidates():
    account = SimpleNamespace(
        record_type="public_account",
        display_name="Linus Torvalds",
        identifiers={"GITHUB_USERNAME": "torvalds"},
        attributes={"login": "torvalds", "company": "Linux Foundation"},
        metadata={},
    )
    assert is_account_candidate_type("public_account") is True
    assert is_account_candidate_record(account) is True
    assert is_identity_candidate_type("public_account") is False
    assert is_identity_candidate_record(account) is False


def test_related_account_is_separate_from_identity_view():
    profile = build_known_identity_profile(
        {"firstName": "Linus", "lastName": "Torvalds", "usernames": "torvalds"}
    )
    rows = [{
        "lane": "Federation",
        "source": "github_public_user",
        "title": "Linus Torvalds",
        "detail": "Login: torvalds · Company: Linux Foundation",
        "type": "public_account",
        "url": "https://github.com/torvalds",
        "seed": "torvalds",
        "seedType": "username",
        "identifiers": {"GITHUB_USERNAME": "torvalds"},
        "candidateOnly": False,
        "accountCandidateEligible": True,
        "identityCandidateEligible": False,
        "_identitySignals": {
            "names": ["Linus Torvalds"],
            "usernames": ["torvalds"],
            "organizations": ["linux foundation"],
        },
    }]
    result = consolidate_result_rows(
        rows,
        seeds=[{"kind": "username", "value": "torvalds"}],
        identity_profile=profile,
    )
    assert result.identity_rows == []
    assert len(result.related_accounts) == 1
    assert result.related_accounts[0]["accountRelationLabel"] == "Related account"
    assert result.related_accounts[0]["identityStatus"] == "not_applicable"


def test_username_clean_view_requires_exact_account_proof():
    good = assess_result_row({
        "lane": "Classic OSINT", "source": "GAU",
        "title": "https://github.com/torvalds", "detail": "Historical Url",
        "type": "historical_url", "url": "https://github.com/torvalds",
        "seed": "torvalds", "seedType": "username", "candidateOnly": False,
    })
    bad = assess_result_row({
        "lane": "Classic OSINT", "source": "GAU",
        "title": "https://gitlab.com/adamstoolkit", "detail": "Historical Url",
        "type": "historical_url", "url": "https://gitlab.com/adamstoolkit",
        "seed": "torvalds", "seedType": "username", "candidateOnly": False,
        "meta": "D0 · torvalds",
    })
    repo = assess_result_row({
        "lane": "Classic OSINT", "source": "GAU",
        "title": "https://github.com/torvalds/linux", "detail": "Historical Url",
        "type": "historical_url", "url": "https://github.com/torvalds/linux",
        "seed": "torvalds", "seedType": "username", "candidateOnly": False,
    })
    assert good.keep_clean and good.pivot_allowed
    assert repo.keep_clean and repo.pivot_allowed
    assert bad.keep_clean is False
    assert bad.pivot_allowed is False


def test_remote_username_identifier_still_routes_as_relevant():
    record = SimpleNamespace(
        display_name="Linus Torvalds",
        record_id="1024025",
        record_type="public_account",
        country=None,
        identifiers={"GITHUB_USERNAME": "torvalds"},
        attributes={"login": "torvalds"},
        metadata={},
    )
    assessment = assess_record_against_seed(_seed("username", "torvalds"), record)
    assert assessment.keep_clean is True
    assert assessment.pivot_allowed is True


def test_commoncrawl_skips_non_object_json_rows():
    try:
        from app.osint.connectors.commoncrawl_connector import CommonCrawlConnector
        from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
    except ModuleNotFoundError:
        pytest.skip("Full OSINT connector runtime is not present in payload-only unit environment")
    connector = CommonCrawlConnector()
    connector.runner = SimpleNamespace(
        run=lambda *args, **kwargs: SimpleNamespace(
            success=True,
            stdout='"not-an-object"\n["also", "not", "object"]\n{"url":"https://example.org/page"}\n',
            stderr="",
            execution_time=0.01,
        )
    )
    request = ConnectorRequest(
        target=OsintTarget(OsintTargetType.DOMAIN, "example.org"),
        timeout=5,
    )
    result = connector.execute(request)
    assert result.total_findings == 1
    assert result.findings[0].value == "https://example.org/page"
    assert result.metadata["non_object_rows_skipped"] == 2


def test_worker_and_qml_expose_related_accounts_contract():
    worker = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert '"relatedAccounts": [' in worker
    assert '"relatedAccounts": len(consolidation.related_accounts or [])' in worker
    assert '{ key: "accounts", label: "Accounts" }' in qml
    assert "runData.relatedAccounts" in qml
    assert "RELATED ACCOUNT" in qml
