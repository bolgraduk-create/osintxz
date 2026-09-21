from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from app.core.ai_factory import create_ai_stack


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        ai_provider="ollama",
        ai_model=None,
        default_model="qwen3:8b",
        ollama_model="qwen3:8b",
        ollama_url="http://localhost:11434",
        openai_api_key=SecretStr("sk-test-secret"),
        openai_model="gpt-5.6",
        openai_reasoning_effort="medium",
        openai_timeout_seconds=120.0,
        openai_store_responses=False,
    )


def test_ai_factory_runtime_override_switches_real_provider_and_model():
    manager, _ = create_ai_stack(
        _config(),
        provider_name="openai",
        model_name="gpt-5.6-terra",
        reasoning_effort="high",
    )

    assert manager.provider_name == "openai"
    assert manager.model_name == "gpt-5.6-terra"
    assert manager.config["reasoning_effort"] == "high"
    assert manager.config["api_key"] == "sk-test-secret"

    local_manager, _ = create_ai_stack(
        _config(),
        provider_name="ollama",
        model_name="qwen3:8b",
    )
    assert local_manager.provider_name == "ollama"
    assert local_manager.model_name == "qwen3:8b"
    assert local_manager.config["host"] == "localhost"
    assert local_manager.config["port"] == 11434


def test_service_container_accepts_per_run_ai_selection():
    source = Path("app/core/service_container.py").read_text(encoding="utf-8")

    assert "ai_provider_name: str | None = None" in source
    assert "ai_model_name: str | None = None" in source
    assert "ai_reasoning_effort: str | None = None" in source
    assert "provider_name=ai_provider_name" in source
    assert "model_name=ai_model_name" in source
    assert "reasoning_effort=ai_reasoning_effort" in source


def test_worker_injects_selected_provider_into_real_analysis_container():
    source = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert "provider_name: str = \"\"" in source
    assert "ai_provider_name=self.provider_name or None" in source
    assert "ai_model_name=self.model or None" in source
    assert "ai_reasoning_effort=self.reasoning_effort or None" in source


def test_analysis_bridge_discovers_ollama_and_passes_selected_provider():
    bridge = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")
    discovery = Path(
        "app/interface/desktop/workers/analysis_provider_discovery_worker.py"
    ).read_text(encoding="utf-8")

    assert "def providerCatalog(" in bridge
    assert "def refreshProviders(" in bridge
    assert "provider_name=selected_provider" in bridge
    assert "Local providers own their model selection" in bridge
    assert 'base_url + "/api/tags"' in discovery
    assert '"ollamaModels"' in discovery
    assert 'payload["ollamaModels"] = discovered' in discovery
    assert "configured-but-not-installed" in discovery


def test_analysis_qml_provider_and_model_controls_are_functional():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert 'property string selectedProvider: ""' in qml
    assert 'text: "PROVIDER"' in qml
    assert "id: providerBox" in qml
    assert "analysisBridge.providerCatalog" in qml
    assert "analysisBridge.refreshProviders()" in qml
    assert "root.applyProvider(" in qml
    assert "root.selectedProvider" in qml
    assert "root.modelIdAt(index)" in qml
    assert 'text: "MODEL"' in qml
    assert 'text: "REASONING"' in qml
    assert 'desktopBridge.hasCurrentCase ? "Run Analysis" : "Select Case"' in qml
    assert "root.selectedProviderReady()" in qml


def test_run_analysis_qml_passes_provider_as_ninth_argument():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    call = qml[qml.index("analysisBridge.runAnalysis("):]
    call = call[: call.index("\n        )") + len("\n        )")]
    assert "root.selectedProvider" in call
