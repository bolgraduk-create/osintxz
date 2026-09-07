from __future__ import annotations

from pathlib import Path

from app.core.service_container import ServiceContainer
import app.database.session as session_module
from app.osint.models import OsintTargetType


def main() -> int:
    session = session_module.create_session()
    try:
        container = ServiceContainer(session)
        worker_text = Path(
            "app/interface/desktop/workers/investigation_search_worker.py"
        ).read_text(encoding="utf-8")

        policy = container.osint_enrichment_execution_service.router.policy

        expected = {
            OsintTargetType.USERNAME: ("account_discovery",),
            OsintTargetType.EMAIL: (
                "email_registration",
                "email_profile_enrichment",
            ),
            OsintTargetType.PHONE: ("phone_enrichment",),
            OsintTargetType.DOMAIN: (
                "domain_discovery",
                "historical_web",
            ),
            OsintTargetType.URL: ("historical_web",),
        }

        checks = [
            (
                "integration service wired",
                hasattr(container, "investigation_target_enrichment_service"),
            ),
            (
                "worker invokes specialized OSINT",
                "investigation_target_enrichment_service.enrich" in worker_text,
            ),
            (
                "worker retains Open-Web",
                "open_web_enrichment_service.enrich" in worker_text,
            ),
            (
                "worker emits OSINT payload",
                '"osint": osint_result' in worker_text,
            ),
        ]

        for target_type, goals in expected.items():
            actual = tuple(
                goal.value
                for goal in policy.default_goals(target_type)
            )
            checks.append(
                (f"{target_type.value} goals", actual == goals)
            )

        print("=" * 84)
        print("M021.16.7.7 ALL EXISTING UI INTEGRATION AUDIT")
        print("=" * 84)

        failed = False
        for label, ok in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
            failed |= not ok

        print("\nRESULT:", "FAIL" if failed else "PASS")
        return 1 if failed else 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
