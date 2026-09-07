from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.osint.capabilities import (
    ConnectorDisposition,
    NetworkMode,
    OSINT_CAPABILITY_CATALOG,
)


def main() -> int:
    connector_files = {
        path.stem
        for path in Path("app/osint/connectors").glob("*_connector.py")
    }
    catalog_modules = set(OSINT_CAPABILITY_CATALOG)

    print("=" * 62)
    print("OSINTXZ M021.0.1 CAPABILITY CATALOG AUDIT")
    print("=" * 62)

    missing = sorted(connector_files - catalog_modules)
    stale = sorted(catalog_modules - connector_files)

    print(f"Connector modules in repository : {len(connector_files)}")
    print(f"Capability catalog entries      : {len(catalog_modules)}")

    if missing:
        print(f"[FAIL] Missing catalog entries: {', '.join(missing)}")
    else:
        print("[PASS] Every connector module has capability metadata.")

    if stale:
        print(f"[FAIL] Stale catalog entries: {', '.join(stale)}")
    else:
        print("[PASS] Catalog contains no stale connector modules.")

    disposition_counts = Counter(
        item.disposition.value
        for item in OSINT_CAPABILITY_CATALOG.values()
    )
    print("\nDisposition:")
    for name in ConnectorDisposition:
        print(f"  {name.value:12} {disposition_counts[name.value]:2}")

    default_items = [
        item
        for item in OSINT_CAPABILITY_CATALOG.values()
        if item.default_enabled
    ]
    print(f"\nAutomatic-enrichment eligible : {len(default_items)}")

    unsafe_defaults = [
        item.display_name
        for item in default_items
        if item.requires_account
        or item.requires_api_key
        or item.network_mode is NetworkMode.ACTIVE
        or item.disposition
        in {
            ConnectorDisposition.CONDITIONAL,
            ConnectorDisposition.SEPARATE,
            ConnectorDisposition.REPLACE,
        }
    ]

    if unsafe_defaults:
        print("[FAIL] Unsafe defaults: " + ", ".join(sorted(unsafe_defaults)))
    else:
        print("[PASS] No credentialed/active/separate connector is default-enabled.")

    print("\nKey policy decisions:")
    for module in (
        "maigret_connector",
        "sherlock_connector",
        "phoneinfoga_connector",
        "ghunt_connector",
        "whatsmyname_connector",
        "commoncrawl_connector",
        "theharvester_connector",
        "nmap_connector",
        "nuclei_connector",
    ):
        item = OSINT_CAPABILITY_CATALOG[module]
        print(
            f"  {item.display_name:18} "
            f"{item.disposition.value:11} "
            f"default={str(item.default_enabled):5} "
            f"recursive={item.recursive_value}"
        )

    if missing or stale or unsafe_defaults:
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS")
    print("Catalog is ready to become the input to M021.1 Pivot Policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
