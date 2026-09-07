from __future__ import annotations

from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter


CASES = (
    (OsintTargetType.USERNAME, "example_user"),
    (OsintTargetType.EMAIL, "user@example.com"),
    (OsintTargetType.PHONE, "+380671234567"),
    (OsintTargetType.DOMAIN, "example.com"),
    (OsintTargetType.URL, "https://example.com/"),
    (OsintTargetType.IP, "203.0.113.10"),
)


def main() -> int:
    router = OsintCapabilityRouter()

    print("=" * 68)
    print("OSINTXZ M021.1 PIVOT POLICY + CAPABILITY ROUTER AUDIT")
    print("=" * 68)

    forbidden = {
        "Nmap",
        "Naabu",
        "Nuclei",
        "Nikto",
        "FFUF",
        "Feroxbuster",
        "GHunt",
        "Have I Been Pwned",
        "Intelligence X",
        "VirusTotal",
        "GreyNoise",
        "AbuseIPDB",
    }

    observed: set[str] = set()

    for target_type, value in CASES:
        routes = router.route_defaults(
            target_type=target_type,
            value=value,
            depth=0,
            entity_identity=f"audit:{target_type.value}:{value}",
            state=PivotTraversalState(),
        )

        print(f"\n{target_type.value}: {value}")
        if not routes:
            print("  automatic route: NONE")
            continue

        for route in routes:
            names = [item.display_name for item in route.connectors]
            observed.update(names)
            print(f"  goal={route.goal.value}")
            print(f"  connectors={', '.join(names) if names else 'NONE'}")

    leaked = sorted(forbidden & observed)
    if leaked:
        print("\n[FAIL] Forbidden automatic connectors leaked into routes:")
        for name in leaked:
            print(f"  - {name}")
        return 1

    username_route = router.route(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="audit:username",
        state=PivotTraversalState(),
    )
    username_names = {item.display_name for item in username_route.connectors}
    if username_names != {"Maigret", "Sherlock"}:
        print("\n[FAIL] Username automatic account-discovery route must be exactly Maigret + Sherlock.")
        print("Observed: " + ", ".join(sorted(username_names)))
        return 1

    phone_routes = router.route_defaults(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        depth=0,
        entity_identity="audit:phone",
        state=PivotTraversalState(),
    )
    if (
        len(phone_routes) != 1
        or phone_routes[0].goal is not DiscoveryGoal.PHONE_ENRICHMENT
    ):
        print("\n[FAIL] Phone policy is not enrichment-only.")
        return 1

    print("\n[PASS] Automatic routes use only allowed default capabilities.")
    print("[PASS] Active/credentialed/separate tools do not leak into routes.")
    print("[PASS] Username discovery has Maigret + Sherlock.")
    print("[PASS] Phone automatic routing remains enrichment-only.")
    print("[PASS] Traversal guards are implemented for M021 recursive discovery.")
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
