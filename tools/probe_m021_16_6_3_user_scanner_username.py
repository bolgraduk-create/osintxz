from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


print("=" * 80)
print("M021.16.6.3 USERNAME ROUTING PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    print("runtime USERNAME connectors:")

    for connector in container.osint_manager.registry.supported(
        OsintTargetType.USERNAME
    ):
        if connector.name in {
            "Sherlock",
            "Maigret",
            "SocialScan",
            "user_scanner",
        }:
            print(
                f" - {connector.name}: "
                f"{connector.__class__.__name__}; "
                f"available={connector.is_available()}"
            )

    route = container.osint_enrichment_execution_service.router.route(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="probe:username",
        state=PivotTraversalState(),
    )

    print()
    print("ACCOUNT_DISCOVERY route:")

    for item in route.connectors:
        print(f" - {item.connector_class}")

finally:
    session.close()

print("PROBE COMPLETE")
