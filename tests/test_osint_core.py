"""
Tests OSINT core architecture.

Checks:

- manager
- registry
- pipeline
- connector registration
- connector metadata
"""

from app.osint.manager import OsintManager
from app.osint.pipeline import OsintPipeline
from app.osint.base_connector import BaseConnector


def main() -> None:

    print("=" * 60)
    print("OSINT CORE TEST")
    print("=" * 60)

    manager = OsintManager()

    pipeline = OsintPipeline(manager)

    connectors = manager.registry.all()

    print(f"Registered connectors: {len(connectors)}")

    assert len(connectors) > 0

    names = set()

    for connector in connectors:

        print(f"[OK] {connector.name}")

        assert isinstance(
            connector,
            BaseConnector,
        )

        assert connector.name
        assert connector.description
        assert connector.supported_targets

        assert callable(
            connector.execute,
        )

        assert callable(
            connector.is_available,
        )

        lower_name = connector.name.lower()

        assert lower_name not in names

        names.add(lower_name)

    print()

    print("Registry OK")

    print(
        f"Pipeline connectors: "
        f"{len(pipeline.available_connectors())}"
    )

    assert (
        len(
            pipeline.available_connectors()
        )
        == len(connectors)
    )

    print()
    print("=" * 60)
    print("OSINT CORE PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()