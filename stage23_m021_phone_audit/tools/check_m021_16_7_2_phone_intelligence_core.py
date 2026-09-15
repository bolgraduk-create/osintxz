from app.osint.capabilities import DiscoveryGoal
from app.osint.manager import OsintManager
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter


def main() -> int:
    print("=" * 72)
    print("M021.16.7.2 PHONE INTELLIGENCE CORE AUDIT")
    print("=" * 72)

    manager = OsintManager()
    supported = manager.registry.supported(OsintTargetType.PHONE)
    for connector in supported:
        print(connector.name, "|", connector.__class__.__name__, "| available=", connector.is_available())

    classes = {item.__class__.__name__ for item in supported}
    route = OsintCapabilityRouter().route(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        goal=DiscoveryGoal.PHONE_ENRICHMENT,
        depth=0,
        entity_identity="audit:phone",
        state=PivotTraversalState(),
    )
    print("\nroute allowed:", route.allowed)
    routed = {item.connector_class for item in route.connectors}
    for item in route.connectors:
        print(item.connector_class, "|", item.disposition, "|", item.network_mode)

    checks = [
        ("LocalPhone registered", "LocalPhoneConnector" in classes),
        ("PhoneInfoga retained", "PhoneInfogaConnector" in classes),
        ("LocalPhone routed", "LocalPhoneConnector" in routed),
        ("PhoneInfoga routed", "PhoneInfogaConnector" in routed),
    ]
    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok
    print("RESULT:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
