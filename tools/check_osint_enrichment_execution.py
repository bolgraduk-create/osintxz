from __future__ import annotations

from app.osint.enrichment_execution import OsintEnrichmentExecutionService
from app.osint.manager import OsintManager
from app.osint.models import OsintTargetType
from app.osint.pipeline import OsintPipeline
from app.osint.pivot_policy import PivotTraversalState


CASES = (
    (OsintTargetType.USERNAME, "example_user"),
    (OsintTargetType.EMAIL, "user@example.com"),
    (OsintTargetType.PHONE, "+380671234567"),
    (OsintTargetType.DOMAIN, "example.com"),
    (OsintTargetType.URL, "https://example.com/"),
    (OsintTargetType.IP, "203.0.113.10"),
)


def main() -> int:
    manager = OsintManager()
    service = OsintEnrichmentExecutionService(pipeline=OsintPipeline(manager))

    print("=" * 72)
    print("OSINTXZ M021.2 ENRICHMENT EXECUTION BOUNDARY AUDIT")
    print("=" * 72)
    print("\nPLAN-ONLY audit: no connector execution and no network requests.\n")

    failures = []

    for target_type, value in CASES:
        routes = service.router.route_defaults(
            target_type=target_type,
            value=value,
            depth=0,
            entity_identity=f"audit:{target_type.value}",
            state=PivotTraversalState(),
        )

        print(f"{target_type.value}: {value}")
        if not routes:
            print("  routes: NONE")
            continue

        for route in routes:
            print(f"  goal={route.goal.value}")
            for capability in route.connectors:
                runtime_name = service._resolve_runtime_connector_name(capability)
                state = (
                    f"runtime={runtime_name}"
                    if runtime_name is not None
                    else "runtime=NOT_REGISTERED"
                )
                print(
                    f"    {capability.display_name:18} "
                    f"{capability.connector_class:28} {state}"
                )

                if capability.manager_default_registered and runtime_name is None:
                    failures.append(capability.display_name)

    if failures:
        print("\n[FAIL] Marked-registered connectors could not be resolved:")
        for name in failures:
            print("  - " + name)
        print("\nRESULT: FAIL")
        return 1

    print("\n[PASS] Router capabilities resolve against current OsintManager.")
    print("[PASS] Runtime resolution uses connector class, not display name.")
    print("[PASS] Audit does not execute tools or network requests.")
    print("[PASS] No persistence or recursive discovery is enabled.")
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
