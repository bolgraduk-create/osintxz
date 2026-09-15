from app.core.service_container import ServiceContainer
import app.database.session as session_module

from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    route = (
        container
        .osint_enrichment_execution_service
        .router
        .route(
            target_type=OsintTargetType.PHONE,
            value="+380671234567",
            goal=DiscoveryGoal.PHONE_ENRICHMENT,
            depth=0,
            entity_identity="probe:phone",
            state=PivotTraversalState(),
        )
    )

    print("allowed:", route.allowed)
    print("connectors:", len(route.connectors))

    for item in route.connectors:
        print(
            item.connector_class,
            "| disposition=",
            item.disposition,
            "| network=",
            item.network_mode,
        )

finally:
    session.close()
