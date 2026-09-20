from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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
from app.registry_intelligence.provider import RegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.router import RegistryQueryRouter
from app.registry_intelligence.source_center import build_registry_center_snapshot


class FakeProvider(RegistryProvider):
    def __init__(self, info: RegistryProviderInfo) -> None:
        self._info = info

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        return RegistryProviderResult(
            provider=self.info.name,
            status=RegistryResultStatus.SUCCESS,
        )


def _info(
    name: str,
    *,
    requires_credentials: bool = False,
    default_enabled: bool = False,
    access_mode: RegistryAccessMode = RegistryAccessMode.API,
) -> RegistryProviderInfo:
    return RegistryProviderInfo(
        name=name,
        display_name=name.upper(),
        domains=frozenset({RegistryDomain.BUSINESS}),
        query_kinds=frozenset({RegistryQueryKind.NAME}),
        countries=frozenset({"GB"}),
        global_scope=False,
        public_data_only=True,
        requires_credentials=requires_credentials,
        default_enabled=default_enabled,
        access_mode=access_mode,
        source_type=RegistrySourceType.OFFICIAL_API,
        trust_score=0.9,
    )


def test_explicit_configured_provider_can_run_even_when_not_default_enabled() -> None:
    registry = RegistryProviderRegistry()
    registry.register(FakeProvider(_info("configured", default_enabled=False)))
    query = RegistryQuery(
        RegistryDomain.BUSINESS,
        RegistryQueryKind.NAME,
        "Example Ltd",
        country="GB",
        sources=("configured",),
    )

    route = RegistryQueryRouter().route(query=query, registry=registry)

    assert route.provider_names == ("configured",)
    assert route.blocked == ()


def test_explicit_provider_never_bypasses_missing_credentials() -> None:
    registry = RegistryProviderRegistry()
    registry.register(
        FakeProvider(
            _info(
                "needs_key",
                requires_credentials=True,
                default_enabled=True,
            )
        )
    )
    query = RegistryQuery(
        RegistryDomain.BUSINESS,
        RegistryQueryKind.NAME,
        "Example Ltd",
        country="GB",
        sources=("needs_key",),
    )

    route = RegistryQueryRouter().route(query=query, registry=registry)

    assert route.providers == ()
    assert len(route.blocked) == 1
    assert "credentials" in route.blocked[0].reason.casefold()


def test_explicit_provider_never_bypasses_manual_or_restricted_access() -> None:
    for mode in (RegistryAccessMode.MANUAL_ASSISTED, RegistryAccessMode.RESTRICTED):
        registry = RegistryProviderRegistry()
        registry.register(
            FakeProvider(
                _info(
                    "guarded",
                    default_enabled=False,
                    access_mode=mode,
                )
            )
        )
        query = RegistryQuery(
            RegistryDomain.BUSINESS,
            RegistryQueryKind.NAME,
            "Example Ltd",
            country="GB",
            sources=("guarded",),
        )
        route = RegistryQueryRouter().route(query=query, registry=registry)
        assert route.providers == ()
        assert len(route.blocked) == 1


def test_automatic_routing_remains_conservative() -> None:
    registry = RegistryProviderRegistry()
    registry.register(FakeProvider(_info("manual_opt_in", default_enabled=False)))
    registry.register(FakeProvider(_info("automatic", default_enabled=True)))
    query = RegistryQuery(
        RegistryDomain.BUSINESS,
        RegistryQueryKind.NAME,
        "Example Ltd",
        country="GB",
    )

    route = RegistryQueryRouter().route(query=query, registry=registry)

    assert route.provider_names == ("automatic",)
    assert {item.provider for item in route.blocked} == {"manual_opt_in"}


def test_registry_center_snapshot_is_runtime_driven_and_network_free() -> None:
    registry = RegistryProviderRegistry()
    registry.register(FakeProvider(_info("ready", default_enabled=True)))
    registry.register(
        FakeProvider(
            _info(
                "needs_key",
                requires_credentials=True,
                default_enabled=True,
            )
        )
    )
    snapshot = build_registry_center_snapshot(
        SimpleNamespace(registry_provider_registry=registry)
    )

    assert snapshot["counts"]["providers"] == 2
    assert snapshot["counts"]["ready"] == 1
    assert snapshot["providerCodes"] == ["needs_key", "ready"]
    rows = {item["code"]: item for item in snapshot["providers"]}
    assert rows["ready"]["runnableExplicit"] is True
    assert rows["needs_key"]["runnableExplicit"] is False
    assert rows["needs_key"]["runtimeStatus"] == "Needs credentials"


def test_registry_center_worker_uses_thread_owned_service_container_and_stable_snapshot() -> None:
    source = Path(
        "app/interface/desktop/workers/registry_center_worker.py"
    ).read_text(encoding="utf-8")

    assert "create_session()" in source
    assert "ServiceContainer(session)" in source
    assert "registry_intelligence_service" in source
    assert "RegistrySearchWorker._snapshot_record" in source
    assert "RegistrySearchWorker._snapshot_provider_result" in source
    assert "RegistrySearchWorker._snapshot_persistence" in source


def test_registry_qml_is_dynamic_and_preserves_legal_identity_guardrails() -> None:
    qml = Path("app/interface/desktop/qml/pages/Registry.qml").read_text(
        encoding="utf-8"
    )
    desktop = Path("app/interface/desktop/desktop_app.py").read_text(
        encoding="utf-8"
    )

    assert "registryBridge.registryCenter" in qml
    assert "registryBridge.search(" in qml
    assert "AUTO · all safe compatible" in qml
    assert "registryBridge.persistLast(desktopBridge.currentCaseId)" in qml
    assert "does not establish identity, guilt, liability or conviction" in qml
    assert 'model: ["EDRPOU", "Company name", "FOP name", "Court case number"]' not in qml
    assert '"registryBridge"' in desktop
