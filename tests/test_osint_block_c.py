"""
Stage test for OSINT Block C.

Checks:

- registration
- availability
- supported targets

Block C:

- Naabu
- Katana
- Waybackurls
- GAU
- Hakrawler
- Subjs
"""

from __future__ import annotations

from app.osint.manager import OsintManager


EXPECTED_CONNECTORS = [

    "Naabu",
    "Katana",
    "Waybackurls",
    "GAU",
    "Hakrawler",
    "Subjs",

]


def print_header() -> None:

    print()
    print("=" * 70)
    print("OSINT BLOCK C TEST")
    print("=" * 70)
    print()


def test_connector(
    manager: OsintManager,
    connector_name: str,
) -> bool:

    connector = manager.registry.get(
        connector_name,
    )

    if connector is None:

        print(
            f"[FAIL] {connector_name:<18} not registered"
        )

        return False

    print(
        f"[ OK ] {connector.name:<18}"
    )

    print(
        f"      Description : {connector.description}"
    )

    print(
        f"      Targets     : "
        + ", ".join(
            target.name
            for target in connector.supported_targets
        )
    )

    print(
        f"      Installed   : {connector.is_available()}"
    )

    print()

    return True


def main() -> None:

    print_header()

    manager = OsintManager()

    passed = 0

    failed = 0

    for connector in EXPECTED_CONNECTORS:

        if test_connector(
            manager,
            connector,
        ):

            passed += 1

        else:

            failed += 1

    print("=" * 70)

    print(
        f"Passed : {passed}"
    )

    print(
        f"Failed : {failed}"
    )

    print("=" * 70)

    if failed == 0:

        print()
        print("BLOCK C PASSED")

    else:

        print()
        print("BLOCK C FAILED")


if __name__ == "__main__":

    main()