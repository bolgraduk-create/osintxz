from pathlib import Path

from app.osint.connectors.user_scanner_connector import UserScannerConnector
from app.osint.models import OsintTargetType


def test_command_is_safe_by_default(tmp_path):
    command = UserScannerConnector._build_command(
        executable="user-scanner",
        target_type=OsintTargetType.EMAIL,
        value="test@example.com",
        output=tmp_path / "result.json",
        timeout=30,
    )

    assert "-e" in command
    assert "test@example.com" in command
    assert "--no-nsfw" in command
    assert "json" in command
    assert "--allow-loud" not in command
    assert "--hudson" not in command
    assert "-P" not in command


def test_registered_records_only():
    payload = {
        "results": [
            {
                "email": "test@example.com",
                "site_name": "Example",
                "status": "Registered",
                "url": "https://example.com",
            },
            {
                "email": "test@example.com",
                "site_name": "Other",
                "status": "Available",
                "url": "https://other.example",
            },
        ]
    }

    records = UserScannerConnector._records(payload)
    accepted = [
        item
        for item in records
        if UserScannerConnector._is_registered(item)
    ]

    assert len(accepted) == 1
    assert accepted[0]["site_name"] == "Example"


def test_username_must_be_explicit_and_plausible():
    assert UserScannerConnector._plausible_username("real_handle")
    assert not UserScannerConnector._plausible_username("test@example.com")


def test_capability_and_runtime_registration_exist():
    capabilities = Path("app/osint/capabilities.py").read_text(encoding="utf-8")
    container = Path("app/core/service_container.py").read_text(encoding="utf-8")

    assert '"user_scanner_connector"' in capabilities
    assert "DiscoveryGoal.EMAIL_REGISTRATION" in capabilities
    assert "M021.16.5.2C1 User Scanner runtime registration" in container
