from __future__ import annotations

from pathlib import Path

CAPABILITIES = Path("app/osint/capabilities.py")
POLICY = Path("app/osint/pivot_policy.py")
CONTAINER = Path("app/core/service_container.py")


def patch_capabilities(text: str) -> str:
    if "gravatar_connector" in text:
        return text

    goal_anchor = '    EMAIL_REGISTRATION = "email_registration"\n'
    if goal_anchor not in text:
        raise RuntimeError("EMAIL_REGISTRATION enum anchor not found.")

    text = text.replace(
        goal_anchor,
        goal_anchor + '    EMAIL_PROFILE_ENRICHMENT = "email_profile_enrichment"\n',
        1,
    )

    insert_after = '''        notes="Registration-presence signal; usually not a public profile finder.",
    ),
'''
    if insert_after not in text:
        raise RuntimeError("Holehe capability anchor not found.")

    gravatar_block = '''        notes="Registration-presence signal; usually not a public profile finder.",
    ),
    _c(
        "gravatar_connector", "GravatarConnector", "Gravatar",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,),
        (
            "public_profile_metadata",
            "public_profile_url",
            "verified_account_url",
        ),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
        notes=(
            "Official public profile source. Only explicit Gravatar "
            "verified_accounts are promoted as account URL pivots."
        ),
    ),
'''
    return text.replace(insert_after, gravatar_block, 1)


def patch_policy(text: str) -> str:
    if "DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT" in text:
        return text

    old = '''    OsintTargetType.EMAIL: (
        DiscoveryGoal.EMAIL_REGISTRATION,
    ),
'''
    new = '''    OsintTargetType.EMAIL: (
        DiscoveryGoal.EMAIL_REGISTRATION,
        DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,
    ),
'''
    if old not in text:
        raise RuntimeError("EMAIL default goals anchor not found.")

    return text.replace(old, new, 1)


def patch_container(text: str) -> str:
    marker = "M021.16.5.1 Gravatar runtime registration"
    if marker in text:
        return text

    anchor = '''        self.osint_manager = (
            OsintManager()
        )
'''
    if anchor not in text:
        raise RuntimeError("OsintManager composition anchor not found.")

    replacement = anchor + '''
        # M021.16.5.1 Gravatar runtime registration
        from app.osint.connectors.gravatar_connector import (
            GravatarConnector,
        )

        self.osint_manager.registry.register(
            GravatarConnector()
        )
'''

    return text.replace(anchor, replacement, 1)


def main() -> int:
    connector = Path("app/osint/connectors/gravatar_connector.py")

    for path in (connector, CAPABILITIES, POLICY, CONTAINER):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        CAPABILITIES: CAPABILITIES.read_text(encoding="utf-8"),
        POLICY: POLICY.read_text(encoding="utf-8"),
        CONTAINER: CONTAINER.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CAPABILITIES: patch_capabilities(originals[CAPABILITIES]),
            POLICY: patch_policy(originals[POLICY]),
            CONTAINER: patch_container(originals[CONTAINER]),
        }

        compile(
            connector.read_text(encoding="utf-8"),
            str(connector),
            "exec",
        )

        for path, value in updated.items():
            compile(value, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_5_1_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")

        path.write_text(value, encoding="utf-8")

    print("[PASS] GravatarConnector installed.")
    print("[PASS] EMAIL_PROFILE_ENRICHMENT goal added.")
    print("[PASS] EMAIL default routing includes profile enrichment.")
    print("[PASS] Gravatar registered in existing OsintManager runtime.")
    print("[PASS] Existing Capability Router / Pipeline reused.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
