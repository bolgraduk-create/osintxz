from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState

print("=" * 80)
print("M021.16.6.2 USERNAME ROUTING PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)
    route = container.osint_enrichment_execution_service.router.route(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="probe:username",
        state=PivotTraversalState(),
    )

    print("allowed:", route.allowed)
    print("connectors:")
    for item in route.connectors:
        print(
            f" - {item.connector_class}: "
            f"default={item.default_enabled}; "
            f"disposition={item.disposition.value}"
        )
finally:
    session.close()

print("PROBE COMPLETE")
