from __future__ import annotations

from uuid import uuid4

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


TARGET = "texnozalypa"


def run(container, use_cache):
    result = (
        container
        .osint_enrichment_execution_service
        .execute(
            target_type=OsintTargetType.USERNAME,
            value=TARGET,
            goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
            depth=0,
            entity_identity=f"probe:{TARGET}:{use_cache}",
            state=PivotTraversalState(),
            case_id=str(uuid4()),
            timeout=120,
            use_cache=use_cache,
            save_raw_output=False,
            include_metadata=True,
            include_related=True,
        )
    )

    print()
    print("=" * 76)
    print("USE_CACHE =", use_cache)
    print("=" * 76)

    for record in result.records:
        print(
            record.runtime_connector_name,
            "|",
            record.result.status,
            "| findings=",
            record.result.total_findings,
            "| error=",
            record.result.error,
        )


session = session_module.create_session()

try:
    container = ServiceContainer(session)

    run(
        container,
        use_cache=False,
    )

    run(
        container,
        use_cache=True,
    )

finally:
    session.close()

print()
print("PROBE COMPLETE")
