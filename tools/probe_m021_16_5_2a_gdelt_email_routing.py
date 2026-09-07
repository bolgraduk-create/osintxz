from __future__ import annotations

import app.database.session as session_module

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


print("=" * 80)
print("M021.16.5.2A GDELT EMAIL ROUTING PROBE")
print("=" * 80)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    query = OpenWebQuery(
        target_type=OsintTargetType.EMAIL,
        value="example@example.com",
        limit=5,
        timeout=15,
    )

    providers = (
        container.open_web_provider_registry
        .automatic_for(query)
    )

    print("automatic EMAIL Open-Web providers:")

    for provider in providers:
        print(
            f" - {provider.info.name}: "
            f"{provider.__class__.__name__}"
        )

finally:
    session.close()

print("PROBE COMPLETE")
