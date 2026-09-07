from __future__ import annotations

import sys

from app.osint.connectors.user_scanner_connector import UserScannerConnector
from app.osint.models import OsintTargetType


def test_supports_username_and_email():
    connector = UserScannerConnector()
    assert OsintTargetType.USERNAME in connector.supported_targets
    assert OsintTargetType.EMAIL in connector.supported_targets


def test_username_command(tmp_path):
    command = UserScannerConnector._build_command(
        executable="ignored.exe",
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        output=tmp_path / "out.json",
        timeout=30,
    )

    assert command[:5] == [
        sys.executable, "-X", "utf8", "-m", "user_scanner"
    ]
    assert "-u" in command
    assert "example_user" in command
    assert "--no-nsfw" in command
    assert "--allow-loud" not in command
    assert "--hudson" not in command


def test_email_command_still_uses_email_flag(tmp_path):
    command = UserScannerConnector._build_command(
        executable="ignored.exe",
        target_type=OsintTargetType.EMAIL,
        value="test@example.com",
        output=tmp_path / "out.json",
        timeout=30,
    )

    assert "-e" in command
    assert "test@example.com" in command
