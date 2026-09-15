from __future__ import annotations

from pathlib import Path

from app.core.service_container import ServiceContainer
import app.database.session as session_module
from app.osint.models import OsintTargetType


def main() -> int:
    session = session_module.create_session()

    try:
        container = ServiceContainer(session)

        worker = Path(
            "app/interface/desktop/workers/"
            "investigation_search_worker.py"
        ).read_text(encoding="utf-8")

        compact = "".join(worker.split())

        policy = (
            container
            .osint_enrichment_execution_service
            .router
            .policy
        )

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
                "unified worker marker",
                "M021.16.7.7.4unifiedspecialized+Open-Webflow"
                in compact,
            ),
            (
                "specialized OSINT call present",
                (
                    "self.container.osint_enrichment_service."
                    "enrich_target("
                    in compact
                ),
            ),
            (
                "Open-Web call present",
                (
                    "self.container.open_web_enrichment_service."
                    "enrich("
                    in compact
                ),
            ),
            (
                "OSINT payload present",
                '"osint":osint_result' in compact,
            ),
            (
                "Open-Web payload present",
                '"open_web":open_web_result' in compact,
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
        print("M021.16.7.7.4 ROBUST WORKER INTEGRATION AUDIT")
        print("=" * 84)

        failed = False

        for label, ok in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
            failed |= not ok

        print()
        print("RESULT:", "FAIL" if failed else "PASS")

        return 1 if failed else 0

    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
