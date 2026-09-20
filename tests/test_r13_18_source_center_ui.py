from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.intelligence_sources.source_center import build_source_center_snapshot


class FakeRemoteAdapter:
    source_code = "fixture_remote"
    capabilities = frozenset({"email", "domain"})
    countries = frozenset()
    global_scope = True
    configured = True
    automatic_enabled = True


class FakeRemoteRegistry:
    def all(self):
        return (FakeRemoteAdapter(),)


class FakeConnector:
    name = "FixtureOSINT"
    description = "Fixture classic connector"
    supported_targets = frozenset({"email"})

    def is_available(self):
        return True


class FakeOsintRegistry:
    def all(self):
        return (FakeConnector(),)


class FakeProvider:
    info = SimpleNamespace(
        name="fixture_registry",
        display_name="Fixture Registry",
        query_kinds=frozenset({"name"}),
        countries=frozenset({"US"}),
        global_scope=False,
        requires_credentials=False,
        automatic_eligible=True,
        access_mode=SimpleNamespace(value="api"),
        sensitive_legal_data=False,
    )


class FakeRegistry:
    def all(self):
        return (FakeProvider(),)


class FakeOpenWeb:
    info = SimpleNamespace(
        name="fixture_web",
        display_name="Fixture Web",
        supported_targets=frozenset({"domain"}),
        requires_credentials=False,
        automatic_eligible=True,
        public_data_only=True,
    )

    def is_available(self):
        return True


class FakeOpenWebRegistry:
    def all(self):
        return (FakeOpenWeb(),)


class FakeCatalog:
    def get(self, code):
        return None

    def all(self):
        return ()


class FakeCoverage:
    def get(self, code):
        return None


class FakeContainer:
    remote_source_adapter_registry = FakeRemoteRegistry()
    intelligence_source_catalog = FakeCatalog()
    remote_source_coverage = FakeCoverage()
    osint_manager = SimpleNamespace(registry=FakeOsintRegistry())
    registry_provider_registry = FakeRegistry()
    open_web_provider_registry = FakeOpenWebRegistry()


def test_source_center_collects_all_runtime_layers_without_network_calls():
    snapshot = build_source_center_snapshot(FakeContainer())
    kinds = {row["kind"] for row in snapshot["sources"]}
    assert kinds == {
        "remote_adapter",
        "osint_connector",
        "registry_provider",
        "open_web_provider",
    }
    assert snapshot["counts"]["total"] == 4
    assert snapshot["counts"]["remoteAdapters"] == 1
    assert snapshot["counts"]["classicConnectors"] == 1
    assert snapshot["counts"]["registryProviders"] == 1
    assert snapshot["counts"]["openWebProviders"] == 1
    assert snapshot["capabilityCodes"] == ["domain", "email"]


def test_new_source_center_is_isolated_from_existing_desktop_bridge():
    desktop_app = Path("app/interface/desktop/desktop_app.py").read_text(encoding="utf-8")
    bridges = Path("app/interface/desktop/bridges/__init__.py").read_text(encoding="utf-8")
    main = Path("app/interface/desktop/qml/Main.qml").read_text(encoding="utf-8")
    sidebar = Path("app/interface/desktop/qml/components/Sidebar.qml").read_text(encoding="utf-8")

    assert "SourceCenterBridge" in bridges
    assert "self.source_bridge = SourceCenterBridge" in desktop_app
    assert 'setContextProperty(\n            "sourceBridge"' in desktop_app
    assert 'case "sources": return "pages/Sources.qml"' in main
    assert '{key:"sources", label:"Sources", icon:"database.svg"}' in sidebar


def test_federated_search_worker_preserves_safe_automatic_boundary():
    worker = Path(
        "app/interface/desktop/workers/federated_source_search_worker.py"
    ).read_text(encoding="utf-8")
    qml = Path("app/interface/desktop/qml/pages/Sources.qml").read_text(encoding="utf-8")

    assert "sources = ()" in worker
    assert "IntelligenceAccessMode.VERIFIED_SCOPE" in worker
    assert "verified_scope=self.verified_scope" in worker
    assert '"rawSecretValuesStored": False' in worker
    assert "All safe compatible sources" in qml
    assert "I confirm this query is within an authorized / verified scope" in qml
    assert "Raw secrets stored: NO" in qml


def test_source_page_exposes_runtime_inventory_and_results():
    qml = Path("app/interface/desktop/qml/pages/Sources.qml").read_text(encoding="utf-8")
    assert 'title: "Source Center"' in qml
    assert 'title: "Federated Results"' in qml
    assert 'model: ["All", "Federation", "Classic OSINT", "Open Web", "Registry", "Catalog"]' in qml
    assert "sourceBridge.search(" in qml
    assert 'desktopBridge.navigateTo("registry")' in qml
    assert 'desktopBridge.navigateTo("osint")' in qml
