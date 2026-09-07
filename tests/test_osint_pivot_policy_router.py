from __future__ import annotations

from app.osint.capabilities import DiscoveryGoal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import (
    OsintPivotPolicy,
    PivotDecisionCode,
    PivotKey,
    PivotPolicyLimits,
    PivotTraversalState,
)
from app.osint.pivot_router import OsintCapabilityRouter


def test_username_routes_only_to_default_account_discovery_sources() -> None:
    router = OsintCapabilityRouter()
    state = PivotTraversalState()

    route = router.route(
        target_type=OsintTargetType.USERNAME,
        value="@Example_User",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=state,
    )

    assert route.allowed
    assert [item.display_name for item in route.connectors] == [
        "Maigret",
        "Sherlock",
        "User Scanner",
        "SocialScan",
    ]


def test_phone_default_route_is_enrichment_not_account_discovery() -> None:
    router = OsintCapabilityRouter()
    state = PivotTraversalState()

    routes = router.route_defaults(
        target_type=OsintTargetType.PHONE,
        value="+380 67 123 45 67",
        depth=0,
        entity_identity="entity:phone:1",
        state=state,
    )

    assert len(routes) == 1
    assert routes[0].goal is DiscoveryGoal.PHONE_ENRICHMENT
    assert [item.display_name for item in routes[0].connectors] == [
        "Local Phone", "PhoneInfoga"
    ]


def test_phone_account_discovery_is_not_invented() -> None:
    router = OsintCapabilityRouter()
    route = router.route(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:phone:1",
        state=PivotTraversalState(),
    )

    assert not route.allowed
    assert route.decision.code is PivotDecisionCode.UNSUPPORTED_GOAL
    assert route.connectors == ()


def test_domain_discovery_prefers_high_recursive_default_sources() -> None:
    router = OsintCapabilityRouter()
    route = router.route(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        depth=0,
        entity_identity="entity:domain:1",
        state=PivotTraversalState(),
    )

    names = [item.display_name for item in route.connectors]
    assert route.allowed
    assert "crt.sh" in names
    assert "Subfinder" in names
    assert "TheHarvester" not in names
    assert "Nmap" not in names


def test_historical_domain_route_has_passive_history_sources() -> None:
    router = OsintCapabilityRouter()
    route = router.route(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        goal=DiscoveryGoal.HISTORICAL_WEB,
        depth=0,
        entity_identity="entity:domain:1",
        state=PivotTraversalState(),
    )

    names = {item.display_name for item in route.connectors}
    assert route.allowed
    assert {"Common Crawl", "Waybackurls", "GAU"}.issubset(names)


def test_active_scanners_never_appear_in_automatic_routes() -> None:
    router = OsintCapabilityRouter()
    names: set[str] = set()

    for target_type, value in (
        (OsintTargetType.DOMAIN, "example.com"),
        (OsintTargetType.IP, "203.0.113.10"),
        (OsintTargetType.URL, "https://example.com/"),
    ):
        for route in router.route_defaults(
            target_type=target_type,
            value=value,
            depth=0,
            entity_identity=f"entity:{target_type.value}:1",
            state=PivotTraversalState(),
        ):
            names.update(item.display_name for item in route.connectors)

    assert "Nmap" not in names
    assert "Naabu" not in names
    assert "Nuclei" not in names
    assert "Nikto" not in names
    assert "FFUF" not in names
    assert "Feroxbuster" not in names


def test_credentialed_connectors_never_appear_in_automatic_routes() -> None:
    router = OsintCapabilityRouter()
    route = router.route(
        target_type=OsintTargetType.EMAIL,
        value="user@example.com",
        goal=DiscoveryGoal.EMAIL_REGISTRATION,
        depth=0,
        entity_identity="entity:email:1",
        state=PivotTraversalState(),
    )

    names = {item.display_name for item in route.connectors}
    assert "GHunt" not in names
    assert "Have I Been Pwned" not in names
    assert "Intelligence X" not in names
    assert {"Holehe", "SocialScan"}.issubset(names)


def test_same_normalized_username_goal_is_blocked_after_visit() -> None:
    policy = OsintPivotPolicy()
    state = PivotTraversalState()

    key = PivotKey.build(
        OsintTargetType.USERNAME,
        "@Example_User",
        DiscoveryGoal.ACCOUNT_DISCOVERY,
    )
    state.mark_visited(
        key=key,
        entity_identity="entity:username:1",
    )

    decision = policy.evaluate(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=1,
        entity_identity="entity:username:1",
        state=state,
    )

    assert not decision.allowed
    assert decision.code is PivotDecisionCode.ALREADY_VISITED


def test_depth_guard_stops_recursive_expansion() -> None:
    policy = OsintPivotPolicy(
        PivotPolicyLimits(max_depth=2),
    )

    decision = policy.evaluate(
        target_type=OsintTargetType.USERNAME,
        value="example",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=3,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert not decision.allowed
    assert decision.code is PivotDecisionCode.MAX_DEPTH_REACHED


def test_per_entity_pivot_budget_is_enforced() -> None:
    policy = OsintPivotPolicy(
        PivotPolicyLimits(max_pivots_per_entity=2),
    )
    state = PivotTraversalState()

    for value in ("example1", "example2"):
        state.mark_visited(
            key=PivotKey.build(
                OsintTargetType.USERNAME,
                value,
                DiscoveryGoal.ACCOUNT_DISCOVERY,
            ),
            entity_identity="entity:username:1",
        )

    decision = policy.evaluate(
        target_type=OsintTargetType.USERNAME,
        value="example3",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=1,
        entity_identity="entity:username:1",
        state=state,
    )

    assert not decision.allowed
    assert decision.code is PivotDecisionCode.PIVOT_BUDGET_EXHAUSTED


def test_global_new_entity_budget_is_enforced() -> None:
    policy = OsintPivotPolicy(
        PivotPolicyLimits(max_new_entities=3),
    )
    state = PivotTraversalState()
    state.add_new_entities(3)

    decision = policy.evaluate(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        depth=1,
        entity_identity="entity:domain:1",
        state=state,
    )

    assert not decision.allowed
    assert decision.code is PivotDecisionCode.ENTITY_BUDGET_EXHAUSTED


def test_hash_has_no_automatic_route_when_only_optional_sources_exist() -> None:
    router = OsintCapabilityRouter()
    routes = router.route_defaults(
        target_type=OsintTargetType.HASH,
        value="abc123",
        depth=0,
        entity_identity="entity:hash:1",
        state=PivotTraversalState(),
    )

    assert routes == ()


def test_routes_are_deterministic() -> None:
    router = OsintCapabilityRouter()

    first = router.route(
        target_type=OsintTargetType.USERNAME,
        value="Example",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:1",
        state=PivotTraversalState(),
    )
    second = router.route(
        target_type=OsintTargetType.USERNAME,
        value="Example",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:1",
        state=PivotTraversalState(),
    )

    assert [item.module for item in first.connectors] == [
        item.module for item in second.connectors
    ]


def test_safe_support_is_included_in_username_account_discovery() -> None:
    router = OsintCapabilityRouter()
    route = router.route(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:support-guard",
        state=PivotTraversalState(),
    )

    names = {item.display_name for item in route.connectors}
    assert names == {"Maigret", "Sherlock", "User Scanner", "SocialScan"}
