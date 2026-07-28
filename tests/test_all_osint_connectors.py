"""
Full OSINT connector integration test.

Checks:

- connector imports
- manager registration
- metadata
- supported targets
- availability detection

Does NOT:

- execute external tools
- call APIs
- perform scans
"""

from __future__ import annotations


from app.osint.manager import OsintManager


def run_test():

    print("=" * 70)
    print("FULL OSINT CONNECTOR TEST")
    print("=" * 70)


    manager = OsintManager()


    connectors = manager.registry.all()


    passed = 0
    failed = 0


    print()

    for connector in connectors:

        try:

            name = connector.name

            description = connector.description

            targets = ", ".join(
                target.value
                for target in connector.supported_targets
            )

            available = connector.is_available()


            print(
                f"[ OK ] {name:<20}"
            )

            print(
                f"      Description : {description}"
            )

            print(
                f"      Targets     : {targets}"
            )

            print(
                f"      Installed   : {available}"
            )

            print()


            passed += 1


        except Exception as exc:


            print(
                f"[FAIL] {connector.__class__.__name__}"
            )

            print(
                f"      Error : {exc}"
            )

            print()


            failed += 1



    print("=" * 70)

    print(
        f"Registered : {len(connectors)}"
    )

    print(
        f"Passed     : {passed}"
    )

    print(
        f"Failed     : {failed}"
    )

    print("=" * 70)



if __name__ == "__main__":

    run_test()