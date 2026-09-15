from app.registry_intelligence.contracts import (
    RegistryAccessMode,
    RegistryDomain,
    RegistryProviderInfo,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryResultStatus,
    RegistrySourceType,
)
from app.registry_intelligence.countries.ukraine import UKRAINE_REGISTRY_SOURCES, ukraine_source
from app.registry_intelligence.provider import RegistryProvider
from app.registry_intelligence.query_detection import detect_registry_query
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter


class FakeProvider(RegistryProvider):
    def __init__(self, *, name, access_mode, default_enabled=True, requires_credentials=False):
        self._info = RegistryProviderInfo(
            name=name,
            display_name=name,
            domains=frozenset({RegistryDomain.BUSINESS}),
            query_kinds=frozenset({RegistryQueryKind.NAME}),
            countries=frozenset({"UA"}),
            access_mode=access_mode,
            source_type=RegistrySourceType.OFFICIAL_API,
            public_data_only=not requires_credentials,
            requires_credentials=requires_credentials,
            default_enabled=default_enabled,
        )

    @property
    def info(self):
        return self._info

    def search(self, query):
        return RegistryProviderResult(provider=self.info.name, status=RegistryResultStatus.SUCCESS)


def test_router_runs_only_automatic_policy_eligible_sources():
    registry = RegistryProviderRegistry()
    registry.register(FakeProvider(name="public", access_mode=RegistryAccessMode.PUBLIC_AUTOMATED))
    registry.register(FakeProvider(name="manual", access_mode=RegistryAccessMode.MANUAL_ASSISTED))
    registry.register(FakeProvider(name="restricted", access_mode=RegistryAccessMode.RESTRICTED))
    registry.register(
        FakeProvider(
            name="contract",
            access_mode=RegistryAccessMode.API,
            requires_credentials=True,
        )
    )

    route = RegistryQueryRouter().route(
        query=RegistryQuery(RegistryDomain.BUSINESS, RegistryQueryKind.NAME, "Example", country="UA"),
        registry=registry,
    )

    assert route.provider_names == ("public",)
    assert {item.provider for item in route.blocked} == {"manual", "restricted", "contract"}


def test_explicit_source_filter_never_falls_back_to_other_provider():
    registry = RegistryProviderRegistry()
    registry.register(FakeProvider(name="one", access_mode=RegistryAccessMode.PUBLIC_AUTOMATED))
    registry.register(FakeProvider(name="two", access_mode=RegistryAccessMode.PUBLIC_AUTOMATED))

    route = RegistryQueryRouter().route(
        query=RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.NAME,
            "Example",
            country="UA",
            sources=("two",),
        ),
        registry=registry,
    )

    assert route.provider_names == ("two",)


def test_missing_explicit_source_is_reported():
    route = RegistryQueryRouter().route(
        query=RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.NAME,
            "Example",
            sources=("not_registered",),
        ),
        registry=RegistryProviderRegistry(),
    )
    assert route.provider_names == ()
    assert route.missing_sources == ("not_registered",)


def test_ukraine_source_matrix_has_unique_codes_and_safe_contracts():
    codes = [source.code for source in UKRAINE_REGISTRY_SOURCES]
    assert len(codes) == len(set(codes))
    assert all(source.country == "UA" for source in UKRAINE_REGISTRY_SOURCES)
    assert all(0.0 <= source.trust_score <= 1.0 for source in UKRAINE_REGISTRY_SOURCES)

    property_source = ukraine_source("ua_property_rights")
    assert property_source is not None
    assert property_source.requires_credentials is True
    assert property_source.automatic_eligible is False

    wanted = ukraine_source("ua_wanted_persons")
    assert wanted is not None
    assert wanted.sensitive_legal_data is True


def test_edrpou_prefix_routes_to_ukraine_business_source():
    query = detect_registry_query("edrpou:12345678")
    assert query is not None
    assert query.country == "UA"
    assert query.kind is RegistryQueryKind.REGISTRATION_ID
    assert query.sources == ("ua_edr_business",)


def test_case_prefix_uses_court_domain_without_identity_claim():
    query = detect_registry_query("case:761/1234/26")
    assert query is not None
    assert query.domain is RegistryDomain.COURT
    assert query.kind is RegistryQueryKind.CASE_NUMBER
