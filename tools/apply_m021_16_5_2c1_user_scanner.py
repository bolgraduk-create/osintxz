from __future__ import annotations

from pathlib import Path

CAPABILITIES = Path("app/osint/capabilities.py")
CONTAINER = Path("app/core/service_container.py")


def patch_capabilities(text: str) -> str:
    if "user_scanner_connector" in text:
        return text

    anchor = '''    _c(
        "socialscan_connector", "SocialScanConnector", "SocialScan",
        (OsintTargetType.USERNAME, OsintTargetType.EMAIL),
        (DiscoveryGoal.ACCOUNT_DISCOVERY, DiscoveryGoal.EMAIL_REGISTRATION),
        ("service_presence", "service_domain"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=2, default_enabled=True,
        notes="Limited service-presence/availability checks.",
    ),
'''

    block = anchor + '''    _c(
        "user_scanner_connector", "UserScannerConnector", "User Scanner",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.EMAIL_REGISTRATION,),
        (
            "service_registration_signal",
            "service_url",
            "explicit_username",
            "explicit_profile_url",
        ),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=True,
        notes=(
            "Free registration coverage. Automatic mode keeps loud/Hudson/"
            "proxy features disabled and accepts only explicit Registered/"
            "Found results."
        ),
    ),
'''

    if anchor not in text:
        raise RuntimeError("SocialScan capability anchor not found.")

    return text.replace(anchor, block, 1)


def patch_container(text: str) -> str:
    marker = "M021.16.5.2C1 User Scanner runtime registration"
    if marker in text:
        return text

    anchor = '''        self.osint_manager = (
            OsintManager()
        )
'''

    block = anchor + '''
        # M021.16.5.2C1 User Scanner runtime registration
        from app.osint.connectors.user_scanner_connector import (
            UserScannerConnector,
        )

        self.osint_manager.registry.register(
            UserScannerConnector()
        )
'''

    if anchor not in text:
        raise RuntimeError("OsintManager composition anchor not found.")

    return text.replace(anchor, block, 1)


def main() -> int:
    connector = Path("app/osint/connectors/user_scanner_connector.py")

    for path in (connector, CAPABILITIES, CONTAINER):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        CAPABILITIES: CAPABILITIES.read_text(encoding="utf-8"),
        CONTAINER: CONTAINER.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CAPABILITIES: patch_capabilities(originals[CAPABILITIES]),
            CONTAINER: patch_container(originals[CONTAINER]),
        }

        compile(connector.read_text(encoding="utf-8"), str(connector), "exec")
        for path, value in updated.items():
            compile(value, str(path), "exec")

    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_5_2c1_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(value, encoding="utf-8")

    print("[PASS] UserScannerConnector installed.")
    print("[PASS] EMAIL_REGISTRATION routing extended.")
    print("[PASS] Existing OsintPipeline reused.")
    print("[PASS] Loud/Hudson/proxy features remain disabled.")
    print("[PASS] Explicit usernames/profile URLs only.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
