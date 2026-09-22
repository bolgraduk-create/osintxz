from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.provider_errors import (
    AIProviderRequestError,
    classify_openai_error,
)
from app.ai.providers.openai_provider import OpenAIProvider


class _CreditBalanceError(Exception):
    status_code = 429
    body = {
        "message": "You have no credits remaining.",
        "type": "insufficient_quota",
        "param": None,
        "code": "credit_balance_exhausted",
    }


class _RateLimitError(Exception):
    status_code = 429
    body = {
        "message": "Rate limit reached.",
        "type": "requests",
        "param": None,
        "code": "rate_limit_exceeded",
    }


class _FailingResponses:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **kwargs):
        raise self.exc


def _connected_provider(exc: Exception) -> OpenAIProvider:
    provider = OpenAIProvider(
        model_name="gpt-5.6-terra",
        api_key="sk-test-secret",
        reasoning_effort="medium",
    )
    provider.client = SimpleNamespace(
        responses=_FailingResponses(exc)
    )
    provider.connected = True
    return provider


def test_credit_balance_exhausted_is_not_rendered_as_raw_sdk_json():
    classified = classify_openai_error(_CreditBalanceError("raw sdk payload"))

    assert isinstance(classified, AIProviderRequestError)
    assert classified.kind == "quota_exhausted"
    assert classified.code == "credit_balance_exhausted"
    assert classified.retryable is False
    assert classified.suggested_action == "switch_to_ollama"
    assert "OpenAI API credits or spend quota are exhausted" in str(classified)
    assert "{'error':" not in str(classified)


def test_temporary_429_stays_distinct_from_exhausted_credit_balance():
    classified = classify_openai_error(_RateLimitError("Rate limit reached"))

    assert classified.kind == "rate_limit"
    assert classified.retryable is True
    assert classified.suggested_action == "retry_or_ollama"


def test_openai_provider_wraps_sdk_failure_in_public_provider_error():
    provider = _connected_provider(_CreditBalanceError("raw error"))

    with pytest.raises(AIProviderRequestError) as captured:
        provider.generate("Analyze the selected investigation.")

    assert captured.value.kind == "quota_exhausted"
    assert captured.value.code == "credit_balance_exhausted"


def test_chat_worker_emits_structured_recovery_metadata():
    source = Path(
        "app/interface/desktop/workers/analysis_chat_worker.py"
    ).read_text(encoding="utf-8")

    assert "public_error_payload(exc)" in source
    assert '"userMessage": self.message' in source
    assert '"provider": (' in source
    assert '"model": self.model' in source


def test_structured_analysis_worker_uses_same_public_error_contract():
    source = Path(
        "app/interface/desktop/workers/investigation_analysis_worker.py"
    ).read_text(encoding="utf-8")

    assert "public_error_payload(exc)" in source
    assert '"error": sanitized_text(error_payload.get("error"))' in source


def test_analysis_bridge_preserves_recovery_fields_without_raw_exception_ui():
    source = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    assert '"errorKind": str(payload.get("errorKind")' in source
    assert '"errorCode": str(payload.get("errorCode")' in source
    assert '"suggestedAction": str(payload.get("suggestedAction")' in source
    assert "def _mark_provider_error(" in source
    assert "def _clear_provider_error(" in source
    assert '"text": error' in source
    assert '"I couldn\'t complete that reply. " + error' not in source


def test_analysis_chat_has_visible_ollama_recovery_and_billing_action():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")

    assert "function providerRuntimeStatusText(info)" in qml
    assert 'if (status === "quota_exhausted") return "credits exhausted"' in qml
    assert "function recoverWithOllama(messageData)" in qml
    assert 'text: root.ollamaReady()' in qml
    assert '"Use Ollama"' in qml
    assert '"Open API billing"' in qml
    assert "https://platform.openai.com/settings/organization/billing/" in qml
    assert "ACTION REQUIRED" in qml
    assert "Theme.danger" in qml


def test_provider_selector_remains_real_after_error_ui_patch():
    qml = Path(
        "app/interface/desktop/qml/pages/Analysis.qml"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/analysis_bridge.py"
    ).read_text(encoding="utf-8")

    assert 'text: "PROVIDER"' in qml
    assert "analysisBridge.providerCatalog" in qml
    assert "analysisBridge.refreshProviders()" in qml
    assert "root.applyProvider(" in qml
    assert "def providerCatalog(" in bridge
