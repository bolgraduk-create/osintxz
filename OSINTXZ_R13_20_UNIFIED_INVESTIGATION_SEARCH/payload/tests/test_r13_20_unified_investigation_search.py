from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.application.unified_investigation_search import (
    UnifiedSeed,
    UnifiedSeedKind,
    build_initial_seeds,
    build_search_plan,
    extract_remote_pivots,
    is_exact_recursive_seed,
    plan_federation_routes,
    registry_queries_for_seed,
)
from app.registry_intelligence.contracts import RegistryDomain, RegistryQueryKind


class FakeAdapter:
    def __init__(self, code, capabilities, *, automatic=True, configured=True, countries=()):
        self.source_code = code
        self.capabilities = frozenset(capabilities)
        self.automatic_enabled = automatic
        self.configured = configured
        self.countries = frozenset(countries)
        self.global_scope = not bool(countries)


class FakeRegistry:
    def __init__(self, *items):
        self.items = items

    def all(self):
        return self.items


def test_structured_form_becomes_typed_deduplicated_seeds() -> None:
    seeds = build_initial_seeds(
        {
            "firstName": "Alice",
            "lastName": "Example",
            "birthDate": "2000-01-02",
            "aliases": "A. Example\nAlice Example",
            "emails": "Alice@Example.org\nalice@example.org",
            "usernames": "alice; alice_dev",
            "country": "US",
            "city": "New York",
            "address": "1 Example Street",
            "organizations": "Example Labs",
            "domains": "example.org",
            "cves": "CVE-2021-44228",
        }
    )
    pairs = {(item.kind, item.value.casefold()) for item in seeds}
    assert (UnifiedSeedKind.PERSON_NAME, "alice example") in pairs
    assert (UnifiedSeedKind.EMAIL, "alice@example.org") in pairs
    assert (UnifiedSeedKind.USERNAME, "alice_dev") in pairs
    assert (UnifiedSeedKind.ORGANIZATION, "example labs") in pairs
    assert (UnifiedSeedKind.DOMAIN, "example.org") in pairs
    assert (UnifiedSeedKind.CVE, "cve-2021-44228") in pairs
    assert sum(1 for item in seeds if item.kind is UnifiedSeedKind.EMAIL) == 1
    assert all(item.country == "US" for item in seeds)


def test_federation_planner_runs_only_automatic_routes_and_exposes_guarded() -> None:
    registry = FakeRegistry(
        FakeAdapter("github_public", {"username", "github_username"}),
        FakeAdapter("explicit_profile", {"username"}, automatic=False),
        FakeAdapter("unrelated", {"domain"}),
    )
    seed = UnifiedSeed(UnifiedSeedKind.USERNAME, "alice")
    automatic, guarded = plan_federation_routes(registry, seed)
    assert [(item.source_code, item.capability) for item in automatic] == [
        ("github_public", "username")
    ]
    assert [(item.source_code, item.automatic) for item in guarded] == [
        ("explicit_profile", False)
    ]


def test_sensitive_capabilities_do_not_enter_generic_name_search() -> None:
    registry = FakeRegistry(
        FakeAdapter("safe_archive", {"name", "archive_search"}),
        FakeAdapter("wanted", {"wanted_name"}),
        FakeAdapter("sanctions", {"sanctions_name"}),
    )
    seed = UnifiedSeed(UnifiedSeedKind.PERSON_NAME, "Alice Example")
    automatic, guarded = plan_federation_routes(registry, seed)
    assert [item.source_code for item in automatic] == ["safe_archive"]
    assert not any(item.source_code in {"wanted", "sanctions"} for item in automatic)
    assert {item.source_code for item in guarded} == {"wanted", "sanctions"}
    assert all(item.automatic is False for item in guarded)


def test_registry_plan_keeps_court_name_search_opt_in() -> None:
    seed = UnifiedSeed(UnifiedSeedKind.PERSON_NAME, "Alice Example", country="US")
    normal = registry_queries_for_seed(seed, include_sensitive_name_routes=False)
    sensitive = registry_queries_for_seed(seed, include_sensitive_name_routes=True)
    assert [(item.domain, item.kind) for item in normal] == [
        (RegistryDomain.BUSINESS, RegistryQueryKind.PERSON_NAME)
    ]
    assert (RegistryDomain.COURT, RegistryQueryKind.NAME) in {
        (item.domain, item.kind) for item in sensitive
    }


def test_exact_case_number_routes_to_court_without_name_inference() -> None:
    seed = UnifiedSeed(UnifiedSeedKind.CASE_NUMBER, "1:23-cv-00001", country="US")
    queries = registry_queries_for_seed(seed)
    assert len(queries) == 1
    assert queries[0].domain is RegistryDomain.COURT
    assert queries[0].kind is RegistryQueryKind.CASE_NUMBER


def test_remote_pivot_extraction_follows_exact_identifiers_not_names() -> None:
    record = SimpleNamespace(
        source="fixture",
        record_id="1",
        country="US",
        identifiers={"email": "alice@example.org", "company_number": "ABC123"},
        attributes={
            "username": "alice_dev",
            "display_name": "Alice Example",
            "website_domain": "example.org",
            "password": "never-store-this",
        },
        metadata={},
    )
    pivots = extract_remote_pivots(record, depth=1, parent_ref="fixture:1")
    by_kind = {item.kind: item for item in pivots}
    assert by_kind[UnifiedSeedKind.EMAIL].value == "alice@example.org"
    assert by_kind[UnifiedSeedKind.USERNAME].value == "alice_dev"
    assert by_kind[UnifiedSeedKind.DOMAIN].value == "example.org"
    assert by_kind[UnifiedSeedKind.REGISTRATION_ID].value == "ABC123"
    assert by_kind[UnifiedSeedKind.PERSON_NAME].candidate_only is True
    assert is_exact_recursive_seed(by_kind[UnifiedSeedKind.EMAIL]) is True
    assert is_exact_recursive_seed(by_kind[UnifiedSeedKind.PERSON_NAME]) is False
    assert "never-store-this" not in repr(pivots)


def test_search_plan_combines_runtime_lanes_without_network_calls() -> None:
    registry = FakeRegistry(
        FakeAdapter("github_public", {"username"}),
        FakeAdapter("dns", {"domain"}),
    )
    seeds = [
        UnifiedSeed(UnifiedSeedKind.USERNAME, "alice"),
        UnifiedSeed(UnifiedSeedKind.DOMAIN, "example.org"),
        UnifiedSeed(UnifiedSeedKind.ORGANIZATION, "Example Labs", country="US"),
    ]
    plan = build_search_plan(adapter_registry=registry, seeds=seeds)
    assert len(plan.seeds) == 3
    assert {item.kind for item in plan.classic_seeds} >= {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.DOMAIN,
    }
    assert {route.source_code for _, route in plan.federation_routes} == {
        "github_public",
        "dns",
    }
    assert any(query.kind is RegistryQueryKind.NAME for _, query in plan.registry_queries)


def test_qml_and_bootstrap_wire_the_new_primary_search_workspace() -> None:
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    desktop = Path("app/interface/desktop/desktop_app.py").read_text(encoding="utf-8")
    bridges = Path("app/interface/desktop/bridges/__init__.py").read_text(encoding="utf-8")
    workers = Path("app/interface/desktop/workers/__init__.py").read_text(encoding="utf-8")

    assert "Known Data" in qml
    assert "Run All Sources" in qml
    assert "Stored Intelligence" in qml
    assert "Follow safe exact pivots" in qml
    assert "includeSensitiveNameRoutes" in qml
    assert "investigationSearchBridge.search" in qml
    assert '"investigationSearchBridge"' in desktop
    assert "InvestigationSearchBridge" in bridges
    assert "UnifiedInvestigationSearchWorker" in workers
