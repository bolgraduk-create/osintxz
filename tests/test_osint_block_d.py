"""
OSINT Block D test.
"""

from app.osint.manager import OsintManager


CONNECTORS = [

    "CloudEnum",
    "S3Scanner",
    "TruffleHog",
    "SecretFinder",
    "GitDorker",
    "Gitleaks",

]


def main():

    manager = OsintManager()

    print("=" * 70)
    print("OSINT BLOCK D TEST")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for name in CONNECTORS:

        connector = manager.registry.get(name)

        if connector is None:

            print(f"[FAIL] {name}")
            failed += 1
            continue

        print(f"[ OK ] {name:<18}")

        print(
            f"      Description : {connector.description}"
        )

        print(
            "      Targets     : "
            + ", ".join(
                target.name
                for target in connector.supported_targets
            )
        )

        print(
            f"      Installed   : {connector.is_available()}"
        )

        print()

        passed += 1

    print("=" * 70)
    print(f"Passed : {passed}")
    print(f"Failed : {failed}")
    print("=" * 70)


if __name__ == "__main__":
    main()