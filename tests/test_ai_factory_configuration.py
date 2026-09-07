"""
Tests for deterministic AI provider/model configuration.
"""

from __future__ import annotations

import pytest

from app.core.ai_factory import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    resolve_ai_configuration,
)


AI_ENVIRONMENT_KEYS = (
    "AI_PROVIDER",
    "AI_MODEL",
    "DEFAULT_MODEL",
    "OLLAMA_MODEL",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_ai_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep every test independent from the developer machine.
    """

    for key in AI_ENVIRONMENT_KEYS:
        monkeypatch.delenv(
            key,
            raising=False,
        )


def test_default_configuration_uses_ollama() -> None:

    assert (
        resolve_ai_configuration()
        ==
        (
            "ollama",
            DEFAULT_OLLAMA_MODEL,
        )
    )


def test_openai_key_does_not_change_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "ollama",
            DEFAULT_OLLAMA_MODEL,
        )
    )


def test_explicit_openai_uses_openai_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "AI_PROVIDER",
        "openai",
    )

    monkeypatch.setenv(
        "OPENAI_MODEL",
        "gpt-test-model",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "openai",
            "gpt-test-model",
        )
    )


def test_openai_ignores_legacy_local_ai_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "AI_PROVIDER",
        "openai",
    )

    monkeypatch.setenv(
        "AI_MODEL",
        "qwen3:8b",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "openai",
            DEFAULT_OPENAI_MODEL,
        )
    )


def test_ollama_model_has_priority_over_legacy_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "AI_PROVIDER",
        "ollama",
    )

    monkeypatch.setenv(
        "AI_MODEL",
        "legacy-model",
    )

    monkeypatch.setenv(
        "OLLAMA_MODEL",
        "ollama-explicit",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "ollama",
            "ollama-explicit",
        )
    )


def test_legacy_ai_model_is_ollama_only_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "AI_MODEL",
        "legacy-qwen",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "ollama",
            "legacy-qwen",
        )
    )


def test_legacy_default_model_is_final_ollama_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "DEFAULT_MODEL",
        "legacy-default",
    )

    assert (
        resolve_ai_configuration()
        ==
        (
            "ollama",
            "legacy-default",
        )
    )


def test_invalid_provider_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setenv(
        "AI_PROVIDER",
        "unknown-provider",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported AI provider",
    ):

        resolve_ai_configuration()
