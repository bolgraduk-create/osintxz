from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType


print("=" * 80)
print("M021.16.4 EMAIL CONNECTOR RUNTIME PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)
    connectors = container.osint_manager.registry.supported(
        OsintTargetType.EMAIL
    )

    print("registered EMAIL connectors:", len(connectors))
    for connector in connectors:
        try:
            available = connector.is_available()
        except Exception as exc:
            available = f"ERROR: {exc}"

        print(
            f" - {connector.name}: "
            f"class={connector.__class__.__name__}; "
            f"available={available}"
        )
finally:
    session.close()

print("PROBE COMPLETE")
