from __future__ import annotations

from pathlib import Path

from app.application.investigation_result_consolidation import consolidate_result_rows


def _account(*, connector: str, service: str, url: str, metadata: dict) -> dict:
    return {
        "lane": "Classic OSINT",
        "source": connector,
        "service": service,
        "title": "texnobreath",
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": url,
        "seed": "texnobreath",
        "seedType": "username",
        "identifiers": {"username": "texnobreath"},
        "findingMetadata": metadata,
        "confidence": 0.94,
        "reliability": 0.90,
        "candidateOnly": False,
        "depth": 0,
    }


def test_cross_source_account_preserves_each_provider_observation():
    url = "https://github.com/texnobreath"
    result = consolidate_result_rows(
        [
            _account(
                connector="Maigret",
                service="GitHub",
                url=url,
                metadata={
                    "registration_confirmed": True,
                    "username": "texnobreath",
                    "site": "GitHub",
                    "profile_id": "123",
                },
            ),
            _account(
                connector="Sherlock",
                service="GitHub",
                url=url,
                metadata={
                    "registration_confirmed": True,
                    "name": "GitHub",
                    "exists": "Claimed",
                },
            ),
        ],
        seeds=[{"kind": "username", "value": "texnobreath"}],
    )

    assert len(result.rows) == 1
    account = result.rows[0]
    observations = account["accountObservations"]

    assert len(observations) == 2
    assert {item["connector"] for item in observations} == {"Maigret", "Sherlock"}
    assert {item["service"] for item in observations} == {"GitHub"}
    assert all(item["url"] == url for item in observations)

    by_connector = {item["connector"]: item for item in observations}
    assert by_connector["Maigret"]["metadata"]["profile_id"] == "123"
    assert by_connector["Sherlock"]["metadata"]["exists"] == "Claimed"


def test_different_platform_accounts_keep_independent_metadata():
    result = consolidate_result_rows(
        [
            _account(
                connector="Maigret",
                service="GitHub",
                url="https://github.com/texnobreath",
                metadata={"bio": "GitHub metadata"},
            ),
            _account(
                connector="Maigret",
                service="Reddit",
                url="https://www.reddit.com/user/texnobreath",
                metadata={"karma": 42},
            ),
        ],
        seeds=[{"kind": "username", "value": "texnobreath"}],
    )

    assert len(result.rows) == 2
    assert all(len(row["accountObservations"]) == 1 for row in result.rows)

    by_url = {row["url"]: row for row in result.rows}
    assert (
        by_url["https://github.com/texnobreath"]["accountObservations"][0]["metadata"]["bio"]
        == "GitHub metadata"
    )
    assert (
        by_url["https://www.reddit.com/user/texnobreath"]["accountObservations"][0]["metadata"]["karma"]
        == 42
    )


def test_search_qml_exposes_account_details_dialog():
    text = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")

    assert "id: accountDetailsDialog" in text
    assert "Account details" in text
    assert "PROVIDER METADATA" in text
    assert "root.openAccountDetails(row.modelData)" in text
    assert "accountObservations" in text
    assert "Open profile" in text
