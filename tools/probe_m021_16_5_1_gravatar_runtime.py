from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


print("=" * 80)
print("M021.16.5.1 GRAVATAR RUNTIME ROUTING PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    registered = [
        (connector.name, connector.__class__.__name__)
        for connector
        in container.osint_manager.registry.supported(
            OsintTargetType.EMAIL
        )
    ]

    print("EMAIL runtime connectors:")
    for name, class_name in registered:
        print(f" - {name}: {class_name}")

    route = (
        container
        .osint_enrichment_execution_service
        .router
        .route(
            target_type=OsintTargetType.EMAIL,
            value="example@example.com",
            goal=DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,
            depth=0,
            entity_identity="probe:email",
            state=PivotTraversalState(),
        )
    )

    print()
    print("EMAIL_PROFILE_ENRICHMENT route:")
    print(" allowed:", route.allowed)
    print(
        " connectors:",
        [item.connector_class for item in route.connectors],
    )

finally:
    session.close()

print("PROBE COMPLETE")
