from __future__ import annotations

import traceback
from uuid import uuid4

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


print("=" * 88)
print("M021.16.6.3.3 USER SCANNER PRODUCTION BOUNDARY DIAGNOSTIC")
print("=" * 88)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    print()
    print("=== RUNTIME REGISTRY ===")

    for connector in (
        container
        .osint_manager
        .registry
        .supported(OsintTargetType.USERNAME)
    ):
        print(
            connector.name,
            "|",
            connector.__class__.__name__,
            "| available=",
            connector.is_available(),
        )

    print()
    print("=== ROUTE ===")

    state = PivotTraversalState()

    route = (
        container
        .osint_enrichment_execution_service
        .router
        .route(
            target_type=OsintTargetType.USERNAME,
            value="texnozalypa",
            goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
            depth=0,
            entity_identity="probe:texnozalypa",
            state=state,
        )
    )

    print("allowed:", route.allowed)

    for item in route.connectors:
        print(
            item.connector_class,
            "| module=",
            item.module,
            "| disposition=",
            item.disposition,
            "| network=",
            item.network_mode,
        )

    print()
    print("=== EXECUTE GOAL ===")

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
    print("route allowed:", result.route.allowed)

    print()
    print("=== CONNECTOR RECORDS ===")

    for record in result.records:
        print()
        print("connector:", record.connector)
        print("capability:", record.capability.connector_class)
        print("status:", record.result.status)
        print("error:", record.result.error)
        print("findings:", record.result.total_findings)
        print("metadata:", record.result.metadata)

except Exception as exc:
    print()
    print("[CRASH]")
    print(type(exc).__name__)
    print(repr(exc))
    traceback.print_exc()

finally:
    session.close()

print()
print("DIAGNOSTIC COMPLETE")
