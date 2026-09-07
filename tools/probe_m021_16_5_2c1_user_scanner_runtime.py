from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType


print("=" * 80)
print("M021.16.5.2C1 USER SCANNER RUNTIME PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    connectors = container.osint_manager.registry.supported(
        OsintTargetType.EMAIL
    )

    for connector in connectors:
        if connector.name == "user_scanner":
            print("connector:", connector.__class__.__name__)
            print("executable:", connector.executable())
            print("available:", connector.is_available())
            break
    else:
        print("[FAIL] User Scanner not registered.")

finally:
    session.close()

print("PROBE COMPLETE")
