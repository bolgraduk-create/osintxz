import sys
from pathlib import Path

from app.osint.connectors.user_scanner_connector import UserScannerConnector
from app.osint.models import OsintTargetType


def test_utf8_module_command(tmp_path):
    command = UserScannerConnector._build_command(
        executable="ignored.exe",
        target_type=OsintTargetType.EMAIL,
        value="test@example.com",
        output=tmp_path / "out.json",
        timeout=30,
    )

    assert command[:5] == [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "user_scanner",
    ]
    assert "--no-nsfw" in command
    assert "--allow-loud" not in command
    assert "--hudson" not in command


def test_no_global_encoding_mutation():
    text = Path(
        "app/osint/connectors/user_scanner_connector.py"
    ).read_text(encoding="utf-8")

    assert "PYTHONIOENCODING" not in text
    assert "M021.16.5.2C1.1 force child UTF-8" in text
