"""
Integration test for OSINT Block B.

Tests:

- registration
- availability
- supported target types
"""

from __future__ import annotations

from app.osint.manager import OsintManager


EXPECTED_CONNECTORS = {

    "TheHarvester",
    "Amass",
    "Subfinder",
    "Assetfinder",
    "DNSX",
    "HTTPX",
    "WhatWeb",

}


def main() -> None:

    manager = OsintManager()

    print("=" * 60)
    print("OSINT BLOCK B TEST")
    print("=" * 60)

    names = {

        connector.name

        for connector
        in manager.registry.all()

    }

    missing = EXPECTED_CONNECTORS - names

    if missing:

        print("\nMissing connectors:")

        for connector in sorted(missing):

            print(f"  - {connector}")

        raise SystemExit(1)

    print("\nRegistered connectors:\n")

    for connector in sorted(

        manager.registry.all(),

        key=lambda c: c.name,

    ):

        if connector.name not in EXPECTED_CONNECTORS:
            continue

        print(f"{connector.name}")

        print(f"  Description : {connector.description}")

        print(
            "  Targets     : "
            + ", ".join(
                target.name
                for target
                in sorted(
                    connector.supported_targets,
                    key=lambda t: t.name,
                )
            )
        )

        print(
            f"  Available   : {connector.is_available()}"
        )

        print()

    print("=" * 60)
    print("BLOCK B PASSED")
    print("=" * 60)


if __name__ == "__main__":

    main()