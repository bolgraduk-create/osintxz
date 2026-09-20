from __future__ import annotations

import json
from pathlib import Path

from app.interface.desktop.bridges.investigation_search_bridge import (
    InvestigationSearchBridge,
)
from app.interface.desktop.workers.account_enrichment_worker import (
    AccountEnrichmentWorker,
)
from app.osint.connectors.maigret_connector import MaigretConnector
from app.osint.result import ResultStatus
from app.osint.runner import ToolExecutionResult


def test_deep_maigret_command_is_single_site_enrichment(tmp_path):
    command = MaigretConnector.build_deep_enrichment_command(
        executable="maigret",
        username="texnobreath",
        site="GitHub",
        output_dir=tmp_path,
        timeout=25,
    )

    assert command[:2] == ["maigret", "texnobreath"]
    assert command[command.index("--site") + 1] == "GitHub"
    assert "--enrich" in command
    assert "--no-recursion" in command
    assert "--no-extracting" not in command
    assert "--top-sites" not in command


def test_site_resolution_accepts_exact_maigret_site(monkeypatch):
    monkeypatch.setattr(
        MaigretConnector,
        "_load_local_site_catalog",
        classmethod(
            lambda cls: {
                "GitHub": {
                    "url": "https://github.com/{username}",
                    "urlMain": "https://github.com",
                }
            }
        ),
    )

    resolved = MaigretConnector.resolve_deep_site(
        username="texnobreath",
        suggested_site="GitHub",
        profile_url="https://github.com/texnobreath",
    )

    assert resolved["supported"] is True
    assert resolved["site"] == "GitHub"


def test_site_resolution_can_use_profile_url_when_provider_label_differs(monkeypatch):
    monkeypatch.setattr(
        MaigretConnector,
        "_load_local_site_catalog",
        classmethod(
            lambda cls: {
                "GitHub": {
                    "url": "https://github.com/{username}",
                    "urlMain": "https://github.com",
                }
            }
        ),
    )

    resolved = MaigretConnector.resolve_deep_site(
        username="texnobreath",
        suggested_site="Github via Sherlock",
        profile_url="https://github.com/texnobreath/",
    )

    assert resolved["supported"] is True
    assert resolved["site"] == "GitHub"
    assert "URL" in resolved["reason"]


def test_unsupported_sherlock_platform_does_not_start_maigret(monkeypatch):
    monkeypatch.setattr(
        MaigretConnector,
        "_load_local_site_catalog",
        classmethod(
            lambda cls: {
                "GitHub": {
                    "url": "https://github.com/{username}",
                    "urlMain": "https://github.com",
                }
            }
        ),
    )
    connector = MaigretConnector()

    class NeverRunner:
        def run(self, *args, **kwargs):
            raise AssertionError("Unsupported site must not start a Maigret process")

    connector.runner = NeverRunner()
    result = connector.deep_enrich(
        username="wixxlexx",
        site="Apple Developer",
        profile_url="https://developer.apple.com/forums/profile/wixxlexx",
        timeout=10,
    )

    assert result.status is ResultStatus.NOT_SUPPORTED
    assert result.metadata["network_request_started"] is False
    assert "not supported" in str(result.error).casefold()


class _FallbackRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str], **kwargs) -> ToolExecutionResult:
        self.commands.append(list(command))
        if "--enrich" in command:
            return ToolExecutionResult(
                success=False,
                return_code=2,
                stdout="",
                stderr="error: unrecognized arguments: --enrich",
                execution_time=0.01,
            )

        working_directory = Path(kwargs["working_directory"])
        (working_directory / "report.json").write_text(
            json.dumps(
                {
                    "GitHub": {
                        "status": "claimed",
                        "url_user": "https://github.com/texnobreath",
                        "bio": "Recovered with page parsing",
                        "fullname": "Example User",
                    }
                }
            ),
            encoding="utf-8",
        )
        return ToolExecutionResult(
            success=True,
            return_code=0,
            stdout="",
            stderr="",
            execution_time=0.02,
        )


def test_deep_enrichment_falls_back_when_local_maigret_lacks_enrich(monkeypatch):
    monkeypatch.setattr(
        MaigretConnector,
        "_load_local_site_catalog",
        classmethod(
            lambda cls: {
                "GitHub": {
                    "url": "https://github.com/{username}",
                    "urlMain": "https://github.com",
                }
            }
        ),
    )
    connector = MaigretConnector()
    connector.runner = _FallbackRunner()
    monkeypatch.setattr(
        MaigretConnector,
        "executable",
        classmethod(lambda cls: "maigret"),
    )

    result = connector.deep_enrich(
        username="texnobreath",
        site="GitHub",
        profile_url="https://github.com/texnobreath",
        timeout=10,
    )

    assert result.status is ResultStatus.SUCCESS
    assert len(connector.runner.commands) == 2
    assert "--enrich" in connector.runner.commands[0]
    assert "--enrich" not in connector.runner.commands[1]
    assert result.metadata["enrich_compatibility_fallback"] is True
    assert result.metadata["secondary_api_enrichment"] is False
    assert result.findings[0].metadata["bio"] == "Recovered with page parsing"
    assert result.findings[0].metadata["fullname"] == "Example User"


def test_account_enrichment_worker_flattens_useful_public_fields():
    fields = AccountEnrichmentWorker._extract_fields(
        [
            {
                "fullname": "Example User",
                "bio": "Open source developer",
                "profile": {
                    "followers": 123,
                    "website": "https://example.test",
                },
                "headers": {"authorization": "must-not-appear"},
                "body": "<html>large response</html>",
            }
        ]
    )

    values = {item["key"]: item["value"] for item in fields}
    assert values["fullname"] == "Example User"
    assert values["bio"] == "Open source developer"
    assert values["profile.followers"] == "123"
    assert values["profile.website"] == "https://example.test"
    assert not any("authorization" in item["value"] for item in fields)
    assert not any(item["key"] in {"headers", "body"} for item in fields)


def test_bridge_prefers_maigret_observation_for_targeted_site():
    account = {
        "service": "Fallback",
        "accountObservations": [
            {
                "connector": "Sherlock",
                "service": "Github",
                "url": "https://github.com/texnobreath",
            },
            {
                "connector": "Maigret",
                "service": "GitHub",
                "url": "https://github.com/texnobreath",
            },
        ],
    }

    selected = InvestigationSearchBridge._preferred_maigret_observation(account)

    assert selected["connector"] == "Maigret"
    assert selected["service"] == "GitHub"


def test_search_qml_exposes_deep_account_enrichment_controls():
    text = Path("app/interface/desktop/qml/pages/Search.qml").read_text(
        encoding="utf-8"
    )

    assert 'text: root.accountEnrichmentBusy ? "Enriching…" : "Deep enrich"' in text
    assert "investigationSearchBridge.deepEnrichAccount(root.selectedAccount)" in text
    assert 'text: "DEEP ENRICHMENT"' in text
    assert "root.accountEnrichment.fields || []" in text
    assert "clearAccountEnrichment()" in text
