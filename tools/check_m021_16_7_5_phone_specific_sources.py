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
        print("M021.16.7.5 PHONE-SPECIFIC PUBLIC SOURCES AUDIT")
        print("=" * 76)

        for provider in providers:
            print(
                provider.info.name,
                "| automatic=",
                provider.info.automatic_eligible,
            )

        targeted = container.targeted_phone_public_sources_provider

        print()
        print("SOURCE RULES:")
        for rule in targeted.rules:
            print(
                rule.name,
                "|",
                rule.tier,
                "|",
                rule.domains,
                "| confidence=",
                rule.confidence,
                "| reliability=",
                rule.reliability,
            )

        checks = [
            (
                "targeted provider registered",
                "targeted_phone_public_sources" in names,
            ),
            ("prozorro present", any(r.name == "prozorro" for r in targeted.rules)),
            ("dzo present", any(r.name == "dzo" for r in targeted.rules)),
            ("youcontrol present", any(r.name == "youcontrol" for r in targeted.rules)),
        ]

        failed = False
        print()

        for label, ok in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
            failed |= not ok

        print("\nRESULT:", "FAIL" if failed else "PASS")
        return 1 if failed else 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
