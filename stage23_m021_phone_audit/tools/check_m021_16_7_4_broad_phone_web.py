from __future__ import annotations

from app.core.service_container import ServiceContainer
import app.database.session as session_module
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


def main() -> int:
    session = session_module.create_session()
    try:
        container = ServiceContainer(session)

        query = OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value="+380671234567",
            limit=5,
            timeout=10,
        )

        providers = container.open_web_provider_registry.automatic_for(query)
        names = [p.info.name for p in providers]

        print("=" * 76)
        print("M021.16.7.4 BROAD PHONE WEB AUDIT")
        print("=" * 76)

        for provider in providers:
            print(
                provider.info.name,
                "| automatic=",
                provider.info.automatic_eligible,
            )

        checks = [
            ("GDELT retained", "gdelt_phone_exact" in names),
            ("SearXNG registered", "searxng_phone_exact" in names),
        ]

        failed = False
        for label, ok in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
            failed |= not ok

        print("RESULT:", "FAIL" if failed else "PASS")
        return 1 if failed else 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
