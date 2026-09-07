from __future__ import annotations

import app.database.session as session_module

from app.core.config import settings
from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


print("=" * 80)
print("M021.16.5.2B BRAVE EMAIL ROUTING PROBE")
print("=" * 80)

configured = (
    settings.brave_search_api_key is not None
    and bool(
        settings.brave_search_api_key
        .get_secret_value()
        .strip()
    )
)

print(
    "BRAVE_SEARCH_API_KEY configured:",
    configured,
)

session = session_module.create_session()

try:
    container = ServiceContainer(session)

    provider = (
        container
        .brave_exact_email_open_web_provider
    )

    print(
        "provider available:",
        provider.is_available(),
    )

    query = OpenWebQuery(
        target_type=OsintTargetType.EMAIL,
        value="example@example.com",
        limit=5,
        timeout=15,
    )

    providers = (
        container
        .open_web_provider_registry
        .automatic_for(query)
    )

    print("automatic EMAIL Open-Web providers:")

    for item in providers:
        print(
            f" - {item.info.name}: "
            f"{item.__class__.__name__}"
        )

finally:
    session.close()

print("PROBE COMPLETE")
