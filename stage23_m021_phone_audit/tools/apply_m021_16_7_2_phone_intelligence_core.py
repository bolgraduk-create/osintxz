from __future__ import annotations

from pathlib import Path
import shutil


def backup(path: Path) -> None:
    dst = path.with_suffix(path.suffix + ".m021_16_7_2_backup")
    if not dst.exists():
        shutil.copy2(path, dst)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> int:
    files = {
        "connectors_init": Path("app/osint/connectors/__init__.py"),
        "manager": Path("app/osint/manager.py"),
        "capabilities": Path("app/osint/capabilities.py"),
        "router": Path("app/osint/pivot_router.py"),
    }
    for path in files.values():
        if not path.exists():
            print(f"[FAIL] Missing: {path}")
            return 1

    # connectors/__init__.py
    path = files["connectors_init"]
    original = path.read_text(encoding="utf-8")
    text = original
    text = replace_once(
        text,
        "from app.osint.connectors.phoneinfoga_connector import (\n    PhoneInfogaConnector,\n)\n",
        "from app.osint.connectors.local_phone_connector import (\n    LocalPhoneConnector,\n)\nfrom app.osint.connectors.phoneinfoga_connector import (\n    PhoneInfogaConnector,\n)\n",
        "connectors import",
    )
    text = replace_once(
        text,
        '    "PhoneInfogaConnector",\n',
        '    "LocalPhoneConnector",\n    "PhoneInfogaConnector",\n',
        "connectors __all__",
    )
    compile(text, str(path), "exec")
    backup(path)
    path.write_text(text, encoding="utf-8")

    # manager.py
    path = files["manager"]
    original = path.read_text(encoding="utf-8")
    text = original
    text = replace_once(
        text,
        "    HoleheConnector,\n    PhoneInfogaConnector,\n",
        "    HoleheConnector,\n    LocalPhoneConnector,\n    PhoneInfogaConnector,\n",
        "manager imports",
    )
    text = replace_once(
        text,
        "            HoleheConnector(),\n            PhoneInfogaConnector(),\n",
        "            HoleheConnector(),\n            LocalPhoneConnector(),\n            PhoneInfogaConnector(),\n",
        "manager registration",
    )
    compile(text, str(path), "exec")
    backup(path)
    path.write_text(text, encoding="utf-8")

    # capabilities.py
    path = files["capabilities"]
    original = path.read_text(encoding="utf-8")
    text = original
    anchor = '''    _c(
        "phoneinfoga_connector", "PhoneInfogaConnector", "PhoneInfoga",
        (OsintTargetType.PHONE,),
        (DiscoveryGoal.PHONE_ENRICHMENT,),
        ("phone_metadata", "country_region", "carrier_metadata"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=1, default_enabled=True,
        notes="Metadata/enrichment only; not the primary phone account-discovery engine.",
    ),
'''
    block = '''    _c(
        "local_phone_connector", "LocalPhoneConnector", "Local Phone",
        (OsintTargetType.PHONE,),
        (DiscoveryGoal.PHONE_ENRICHMENT,),
        (
            "canonical_phone", "phone_metadata", "country_region",
            "carrier_metadata", "line_type", "timezone",
            "exact_search_variants",
        ),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
        notes="Primary local phone metadata source; no network and no ownership inference.",
    ),
''' + anchor
    text = replace_once(text, anchor, block, "capability phone block")
    compile(text, str(path), "exec")
    backup(path)
    path.write_text(text, encoding="utf-8")

    # pivot_router.py
    path = files["router"]
    original = path.read_text(encoding="utf-8")
    text = original
    old = "        if goal is DiscoveryGoal.ACCOUNT_DISCOVERY:\n"
    new = "        if goal in {\n            DiscoveryGoal.ACCOUNT_DISCOVERY,\n            DiscoveryGoal.PHONE_ENRICHMENT,\n        }:\n"
    if old in text:
        text = text.replace(old, new, 1)
    # A second ACCOUNT_DISCOVERY guard exists for network modes.
    if old in text:
        text = text.replace(old, new, 1)
    compile(text, str(path), "exec")
    backup(path)
    path.write_text(text, encoding="utf-8")

    print("[PASS] LocalPhone connector exported and registered.")
    print("[PASS] LocalPhone CORE/PASSIVE capability added.")
    print("[PASS] PHONE_ENRICHMENT now allows passive SUPPORT providers.")
    print("[PASS] PhoneInfoga retained as secondary SUPPORT.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
