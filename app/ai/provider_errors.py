"""Stable, UI-safe AI provider request errors.

Provider SDK exceptions often contain implementation details, long JSON payloads,
URLs, or request metadata that should not be rendered directly in the desktop UI.
This module converts them into a small public contract while preserving the
original exception as the Python cause for logs/debugging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AIProviderErrorDetails:
    provider: str
    kind: str
    code: str
    message: str
    retryable: bool
    status_code: int | None = None
    suggested_action: str = ""


class AIProviderRequestError(RuntimeError):
    """Public-facing provider failure with structured recovery metadata."""

    def __init__(self, details: AIProviderErrorDetails) -> None:
        super().__init__(details.message)
        self.details = details
        self.provider = details.provider
        self.kind = details.kind
        self.code = details.code
        self.retryable = details.retryable
        self.status_code = details.status_code
        self.suggested_action = details.suggested_action

    def to_public_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "errorKind": self.kind,
            "errorCode": self.code,
            "error": str(self),
            "retryable": bool(self.retryable),
            "statusCode": self.status_code,
            "suggestedAction": self.suggested_action,
        }


def classify_openai_error(exc: Exception) -> AIProviderRequestError:
    """Translate an OpenAI SDK/network exception into a stable UI-safe error."""

    status_code = _int_or_none(getattr(exc, "status_code", None))
    body = getattr(exc, "body", None)
    error_obj: Any = None
    if isinstance(body, dict):
        error_obj = body.get("error", body)

    code = ""
    error_type = ""
    if isinstance(error_obj, dict):
        code = str(error_obj.get("code") or "").strip()
        error_type = str(error_obj.get("type") or "").strip()

    # The SDK may expose code directly on the exception.
    if not code:
        code = str(getattr(exc, "code", "") or "").strip()

    normalized = (code or error_type).casefold()
    raw = str(exc or "").casefold()

    if normalized in {
        "credit_balance_exhausted",
        "organization_usage_limit_exceeded",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
    } or (
        status_code == 429
        and (
            "insufficient_quota" in raw
            or "credit_balance_exhausted" in raw
            or "no credits" in raw
        )
    ):
        return AIProviderRequestError(
            AIProviderErrorDetails(
                provider="openai",
                kind="quota_exhausted",
                code=code or normalized or "insufficient_quota",
                message=(
                    "OpenAI API credits or spend quota are exhausted. "
                    "Add API credits / raise the applicable limit, or switch "
                    "the Provider to Ollama."
                ),
                retryable=False,
                status_code=status_code or 429,
                suggested_action="switch_to_ollama",
            )
        )

    if status_code == 429 or "rate limit" in raw:
        return AIProviderRequestError(
            AIProviderErrorDetails(
                provider="openai",
                kind="rate_limit",
                code=code or "rate_limit",
                message=(
                    "OpenAI rate limit reached. Wait briefly and retry, "
                    "or switch the Provider to Ollama."
                ),
                retryable=True,
                status_code=status_code or 429,
                suggested_action="retry_or_ollama",
            )
        )

    if status_code == 401 or "authentication" in raw or "invalid api key" in raw:
        return AIProviderRequestError(
            AIProviderErrorDetails(
                provider="openai",
                kind="authentication",
                code=code or "authentication_error",
                message=(
                    "OpenAI rejected the configured API key. "
                    "Check OPENAI_API_KEY or switch the Provider to Ollama."
                ),
                retryable=False,
                status_code=status_code or 401,
                suggested_action="check_api_key",
            )
        )

    if status_code == 403 or "permission" in raw:
        return AIProviderRequestError(
            AIProviderErrorDetails(
                provider="openai",
                kind="permission",
                code=code or "permission_denied",
                message=(
                    "OpenAI denied access to this request or model. "
                    "Check project/model permissions or select another provider."
                ),
                retryable=False,
                status_code=status_code or 403,
                suggested_action="check_permissions",
            )
        )

    if (
        "timeout" in raw
        or "timed out" in raw
        or "connection" in raw
        or "network" in raw
    ):
        return AIProviderRequestError(
            AIProviderErrorDetails(
                provider="openai",
                kind="network",
                code=code or "network_error",
                message=(
                    "OpenAI could not be reached. Check the connection and retry, "
                    "or switch the Provider to Ollama."
                ),
                retryable=True,
                status_code=status_code,
                suggested_action="retry_or_ollama",
            )
        )

    return AIProviderRequestError(
        AIProviderErrorDetails(
            provider="openai",
            kind="request_failed",
            code=code or "request_failed",
            message=(
                "OpenAI could not complete the request. "
                "Check the application log for technical details."
            ),
            retryable=False,
            status_code=status_code,
            suggested_action="check_logs",
        )
    )


def public_error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, AIProviderRequestError):
        return exc.to_public_payload()
    return {
        "provider": "",
        "errorKind": "application_error",
        "errorCode": "",
        "error": str(exc or "AI request failed."),
        "retryable": False,
        "statusCode": None,
        "suggestedAction": "check_logs",
    }


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "AIProviderErrorDetails",
    "AIProviderRequestError",
    "classify_openai_error",
    "public_error_payload",
]
