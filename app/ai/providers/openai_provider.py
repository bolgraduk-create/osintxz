"""OpenAI Responses API provider for OSINTXZ analysis.

R13.28a replaces the legacy Chat Completions path with the Responses API while
preserving the existing BaseProvider.generate(prompt, **kwargs) contract.

Security/privacy boundaries:
- API keys are injected from the composition root and never serialized.
- response storage is disabled by default.
- no web/file/computer tools are enabled implicitly; investigation analysis is
  grounded only in the context supplied by the application's RAG pipeline.
"""

from __future__ import annotations

from typing import Any

from app.ai.providers.base_provider import BaseProvider


_ALLOWED_REASONING_EFFORTS = {
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


class OpenAIProvider(BaseProvider):
    """OpenAI implementation backed by the Responses API."""

    def __init__(
        self,
        model_name: str = "gpt-5.6",
        api_key: str | None = None,
        reasoning_effort: str = "medium",
        timeout_seconds: float = 120.0,
        store_responses: bool = False,
        **config: Any,
    ) -> None:
        super().__init__(model_name, **config)

        self.api_key = str(api_key or "").strip() or None
        self.reasoning_effort = self._normalize_reasoning_effort(
            reasoning_effort
        )
        self.timeout_seconds = max(1.0, float(timeout_seconds or 120.0))
        self.store_responses = bool(store_responses)
        self.client: Any | None = None

    # ==========================================================
    # Lifecycle
    # ==========================================================

    def initialize(self) -> None:
        """Create the SDK client without making a network request."""

        self.connected = False

        if not self.api_key:
            self.client = None
            return

        try:
            from openai import OpenAI
        except ImportError:
            self.client = None
            return

        self.client = OpenAI(
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )

    def connect(self) -> bool:
        """Mark the configured SDK client ready for lazy network execution.

        We intentionally do not call models.list() here. The first actual
        analysis request is the authoritative network/authentication check and
        avoids an extra API request every time the app initializes AI.
        """

        self.connected = bool(
            self.client is not None
            and self.api_key
        )
        return self.connected

    # ==========================================================
    # Generation
    # ==========================================================

    def generate(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """Generate text through OpenAI Responses API."""

        if not self.connected or self.client is None:
            raise RuntimeError("OpenAI provider is not connected")

        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("OpenAI prompt cannot be empty.")

        request: dict[str, Any] = {
            "model": self.model_name,
            "input": normalized_prompt,
            "store": self.store_responses,
        }

        # Existing higher-level services may still use the old max_tokens name.
        # Normalize it to the Responses API name without changing those callers.
        options = dict(kwargs)
        if (
            "max_tokens" in options
            and "max_output_tokens" not in options
        ):
            options["max_output_tokens"] = options.pop("max_tokens")

        # Storage is an application-level privacy decision, not a per-prompt
        # override. Drop caller-provided values so investigation code cannot
        # accidentally enable remote response storage.
        options.pop("store", None)

        reasoning = options.pop("reasoning", None)
        if reasoning is None and self.reasoning_effort != "none":
            reasoning = {"effort": self.reasoning_effort}
        if reasoning is not None:
            request["reasoning"] = reasoning

        request.update(options)

        response = self.client.responses.create(**request)
        output_text = str(
            getattr(response, "output_text", "")
            or ""
        ).strip()

        if not output_text:
            raise ValueError("OpenAI Responses API returned empty output.")

        return output_text

    # ==========================================================
    # Information
    # ==========================================================

    def get_model_info(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "model": self.model_name,
            "connected": self.connected,
            "configured": bool(self.api_key),
            "api": "responses",
            "reasoning_effort": self.reasoning_effort,
            "store_responses": self.store_responses,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "type": "openai",
            "model": self.model_name,
            "api": "responses",
            "reasoning_effort": self.reasoning_effort,
            "store_responses": self.store_responses,
            "configured": bool(self.api_key),
            "status": (
                "ready"
                if self.connected
                else (
                    "configured"
                    if self.api_key
                    else "not_configured"
                )
            ),
        }

    @staticmethod
    def _normalize_reasoning_effort(value: Any) -> str:
        normalized = str(value or "medium").strip().casefold()
        if normalized not in _ALLOWED_REASONING_EFFORTS:
            allowed = ", ".join(sorted(_ALLOWED_REASONING_EFFORTS))
            raise ValueError(
                "Unsupported OpenAI reasoning effort "
                f"'{normalized}'. Supported values: {allowed}."
            )
        return normalized
