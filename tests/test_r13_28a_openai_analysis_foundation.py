from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr

from app.ai.providers.openai_provider import OpenAIProvider
from app.core.ai_factory import create_ai_stack


class _FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        return SimpleNamespace(output_text="Grounded analysis result")


class _FakeClient:
    def __init__(self) -> None:
        self.responses = _FakeResponses()


def _openai_config(**overrides):
    values = {
        "ai_provider": "openai",
        "openai_model": "gpt-5.6",
        "openai_api_key": SecretStr("sk-test-secret"),
        "openai_reasoning_effort": "medium",
        "openai_timeout_seconds": 120.0,
        "openai_store_responses": False,
        "ollama_model": None,
        "ai_model": None,
        "default_model": "llama3.1:8b",
        "ollama_url": "http://localhost:11434",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_openai_provider_uses_responses_api_contract():
    provider = OpenAIProvider(
        model_name="gpt-5.6",
        api_key="sk-test-secret",
        reasoning_effort="high",
        store_responses=False,
    )
    client = _FakeClient()
    provider.client = client
    provider.connected = True

    result = provider.generate(
        "Analyze this investigation context.",
        max_tokens=900,
        store=True,
    )

    assert result == "Grounded analysis result"
    assert len(client.responses.calls) == 1

    request = client.responses.calls[0]
    assert request["model"] == "gpt-5.6"
    assert request["input"] == "Analyze this investigation context."
    assert request["reasoning"] == {"effort": "high"}
    assert request["store"] is False
    assert request["max_output_tokens"] == 900
    assert "max_tokens" not in request


def test_openai_provider_never_exposes_api_key_in_metadata():
    provider = OpenAIProvider(
        model_name="gpt-5.6",
        api_key="sk-super-secret",
        reasoning_effort="medium",
    )

    metadata_text = repr(provider.metadata()) + repr(provider.get_model_info())

    assert "sk-super-secret" not in metadata_text
    assert provider.metadata()["configured"] is True
    assert provider.metadata()["store_responses"] is False
    assert provider.get_model_info()["api"] == "responses"


def test_openai_provider_missing_key_stays_not_configured():
    provider = OpenAIProvider(
        model_name="gpt-5.6",
        api_key=None,
    )

    provider.initialize()

    assert provider.client is None
    assert provider.connect() is False
    assert provider.metadata()["status"] == "not_configured"


def test_openai_reasoning_effort_can_be_disabled():
    provider = OpenAIProvider(
        model_name="gpt-5.6",
        api_key="sk-test",
        reasoning_effort="none",
    )
    client = _FakeClient()
    provider.client = client
    provider.connected = True

    provider.generate("test")

    request = client.responses.calls[0]
    assert "reasoning" not in request
    assert request["store"] is False


def test_create_ai_stack_injects_secret_only_into_runtime_manager_config():
    manager, analyzer = create_ai_stack(_openai_config())

    assert manager.provider_name == "openai"
    assert manager.model_name == "gpt-5.6"
    assert manager.config["api_key"] == "sk-test-secret"
    assert manager.config["reasoning_effort"] == "medium"
    assert manager.config["store_responses"] is False
    assert analyzer.metadata()["type"] == "ai_analyzer"


def test_openai_sdk_is_declared_as_runtime_dependency():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"openai>=3.16.0,<4.0.0"' in pyproject


def test_ai_factory_does_not_read_environment_directly():
    source = Path("app/core/ai_factory.py").read_text(encoding="utf-8")

    assert "import os" not in source
    assert "os.getenv" not in source
    assert "from app.core.config import Settings, settings" in source


def test_central_settings_define_private_openai_configuration():
    source = Path("app/core/config.py").read_text(encoding="utf-8")

    assert "openai_api_key: SecretStr | None = None" in source
    assert 'openai_model: str = "gpt-5.6"' in source
    assert 'openai_reasoning_effort: str = "medium"' in source
    assert "openai_store_responses: bool = False" in source


def test_env_example_never_contains_a_real_openai_key():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY=" in env_example
    assert "OPENAI_MODEL=gpt-5.6" in env_example
    assert "OPENAI_STORE_RESPONSES=false" in env_example
    assert "sk-" not in env_example


def test_provider_source_uses_responses_not_chat_completions():
    source = Path(
        "app/ai/providers/openai_provider.py"
    ).read_text(encoding="utf-8")

    assert "self.client.responses.create" in source
    assert "chat.completions" not in source
    assert '"store": self.store_responses' in source
