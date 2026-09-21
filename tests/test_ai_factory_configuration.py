"""Tests for deterministic AI provider/model configuration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.ai_factory import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    resolve_ai_configuration,
)


def _config(**overrides):
    values = {
        "ai_provider": "ollama",
        "openai_model": DEFAULT_OPENAI_MODEL,
        "openai_api_key": None,
        "ollama_model": None,
        "ai_model": None,
        "default_model": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_default_configuration_uses_ollama() -> None:
    assert resolve_ai_configuration(_config()) == (
        "ollama",
        DEFAULT_OLLAMA_MODEL,
    )


def test_openai_key_does_not_change_provider() -> None:
    assert resolve_ai_configuration(
        _config(openai_api_key="test-key")
    ) == (
        "ollama",
        DEFAULT_OLLAMA_MODEL,
    )


def test_explicit_openai_uses_openai_model() -> None:
    assert resolve_ai_configuration(
        _config(
            ai_provider="openai",
            openai_model="gpt-test-model",
        )
    ) == (
        "openai",
        "gpt-test-model",
    )


def test_openai_ignores_legacy_local_ai_model() -> None:
    assert resolve_ai_configuration(
        _config(
            ai_provider="openai",
            ai_model="qwen3:8b",
        )
    ) == (
        "openai",
        DEFAULT_OPENAI_MODEL,
    )


def test_ollama_model_has_priority_over_legacy_model() -> None:
    assert resolve_ai_configuration(
        _config(
            ollama_model="ollama-explicit",
            ai_model="legacy-model",
            default_model="legacy-default",
        )
    ) == (
        "ollama",
        "ollama-explicit",
    )


def test_legacy_ai_model_is_ollama_only_fallback() -> None:
    assert resolve_ai_configuration(
        _config(
            ai_model="legacy-qwen",
            default_model="legacy-default",
        )
    ) == (
        "ollama",
        "legacy-qwen",
    )


def test_legacy_default_model_is_final_ollama_fallback() -> None:
    assert resolve_ai_configuration(
        _config(default_model="legacy-default")
    ) == (
        "ollama",
        "legacy-default",
    )


def test_invalid_provider_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported AI provider",
    ):
        resolve_ai_configuration(
            _config(ai_provider="unknown-provider")
        )
