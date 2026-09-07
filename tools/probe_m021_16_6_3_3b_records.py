from __future__ import annotations

from uuid import uuid4

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


print("=" * 88)
print("M021.16.6.3.3B PRODUCTION CONNECTOR RECORDS")
print("=" * 88)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    result = (
        container
        .osint_enrichment_execution_service
        .execute(
            target_type=OsintTargetType.USERNAME,
            value="texnozalypa",
            goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
            depth=0,
            entity_identity="probe:texnozalypa",
            state=PivotTraversalState(),
            case_id=str(uuid4()),
            timeout=120,
            use_cache=False,
            save_raw_output=False,
            include_metadata=True,
            include_related=True,
        )
    )

    print("aggregate status:", result.status)
    print("records:", len(result.records))

    for index, record in enumerate(
        result.records,
        start=1,
    ):
        print()
        print("=" * 60)
        print("RECORD", index)
        print("=" * 60)

        print(
            "capability:",
            record.capability.connector_class,
        )

        print(
            "runtime_connector_name:",
            record.runtime_connector_name,
        )

        print(
            "result.connector:",
            record.result.connector,
        )

        print(
            "status:",
            record.result.status,
        )

        print(
            "error:",
            record.result.error,
        )

        print(
            "findings:",
            record.result.total_findings,
        )

        print(
            "metadata:",
            record.result.metadata,
        )

        if (
            record.capability.connector_class
            == "UserScannerConnector"
        ):
            print()
            print(
                "=== USER SCANNER FINDINGS ==="
            )

            for finding in record.result.findings[:30]:
                print(
                    finding.category,
                    "|",
                    finding.value,
                    "|",
                    finding.url,
                )

finally:
    session.close()

print()
print("PROBE COMPLETE")
