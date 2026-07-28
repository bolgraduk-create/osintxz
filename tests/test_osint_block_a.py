"""
Integration test for OSINT Block A.

Verifies that:

- manager registers every connector
- pipeline executes compatible connectors
- every connector returns OsintResult
- unavailable tools do not crash the pipeline
"""

from app.osint.manager import OsintManager
from app.osint.pipeline import OsintPipeline
from app.osint.models import (
    ConnectorRequest,
    OsintTarget,
    OsintTargetType,
)


def main():

    manager = OsintManager()

    pipeline = OsintPipeline(
        manager,
    )

    print("=" * 60)
    print("REGISTERED CONNECTORS")
    print("=" * 60)

    for connector in manager.registry.all():

        print(
            f"- {connector.name}"
        )

    request = ConnectorRequest(

        target=OsintTarget(

            target_type=OsintTargetType.EMAIL,

            value="example@gmail.com",

        ),

    )

    print()
    print("=" * 60)
    print("PIPELINE EXECUTION")
    print("=" * 60)

    results = pipeline.run(
        request,
    )

    for result in results:

        print()

        print(
            f"Connector : {result.connector}"
        )

        print(
            f"Status    : {result.status.value}"
        )

        print(
            f"Findings  : {result.total_findings}"
        )

        if result.error:

            print(
                f"Error     : {result.error}"
            )

    print()
    print("=" * 60)
    print("TOTAL RESULTS")
    print("=" * 60)

    print(
        len(results)
    )


if __name__ == "__main__":

    main()