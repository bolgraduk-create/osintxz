from __future__ import annotations

from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
import app.database.session as session_module


def main() -> int:
    print("=" * 76)
    print("M021.16.7.3 EXACT PHONE OPEN-WEB AUDIT")
    print("=" * 76)

    session = session_module.create_session()
    failed = False

    try:
        container = ServiceContainer(session)
        providers = container.open_web_provider_registry.all()

        print("\nPROVIDERS:")
        for provider in providers:
            print(
                provider.info.name,
                "| targets=",
                sorted(item.value for item in provider.info.supported_targets),
                "| automatic=",
                provider.info.automatic_eligible,
            )

        query = OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value="+380671234567",
            limit=5,
            timeout=10,
        )

        automatic = container.open_web_provider_registry.automatic_for(query)
        names = {provider.info.name for provider in automatic}

        checks = [
            ("gdelt_phone_exact registered", "gdelt_phone_exact" in {p.info.name for p in providers}),
            ("gdelt_phone_exact automatic for PHONE", "gdelt_phone_exact" in names),
            ("Common Crawl not misused for PHONE", "common_crawl" not in names),
        ]

        print("\nCHECKS:")
        for label, ok in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
            failed |= not ok
    finally:
        session.close()

    print("\nRESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
