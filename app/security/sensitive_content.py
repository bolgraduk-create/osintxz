"""Display/prompt boundary for credential and secret material.

This module is deliberately conservative: it preserves ordinary OSINT
identifiers (emails, usernames, domains, hashes) while removing values that
look like authentication secrets. It is safe to use both before remote AI
execution and before rendering/persisting Analysis Workspace snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


REDACTED = "[REDACTED SECRET]"
PRIVATE_KEY_REDACTED = "[PRIVATE KEY REDACTED]"


@dataclass(frozen=True, slots=True)
class SensitiveTextResult:
    text: str
    redacted: bool
    redaction_count: int


_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN\s+(?:[A-Z0-9 ]+\s+)?PRIVATE KEY-----.*?"
    r"-----END\s+(?:[A-Z0-9 ]+\s+)?PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)

_NAMED_SECRET_RE = re.compile(
    r"(?i)\b("
    r"password|passwd|pwd|passphrase|"
    r"client[ _-]*secret|api[ _-]*key|secret[ _-]*key|"
    r"access[ _-]*token|refresh[ _-]*token|auth[ _-]*token|"
    r"authorization"
    r")\b(\s*[:=]\s*)([\"']?)([^\s,;\"']{4,})([\"']?)"
)

_AUTHORIZATION_HEADER_RE = re.compile(
    r"(?im)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[^\s,;]+"
)

_BEARER_RE = re.compile(
    r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"
)

_BASIC_AUTH_URL_RE = re.compile(
    r"(?i)(https?://[^\s:/@]+:)([^\s/@]{2,})(@)"
)

_EMAIL_SECRET_PAIR_RE = re.compile(
    r"(?i)(\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}:)"
    r"([^\s,;|]{4,})"
)

_DOMAIN_USER_SECRET_RE = re.compile(
    r"(?i)(\b(?:https?://)?(?:[A-Z0-9-]+\.)+[A-Z]{2,}"
    r":[^:\s|]{1,128}:)([^:\s|]{4,})"
)

_KNOWN_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\."
        r"[A-Za-z0-9_-]{8,}\."
        r"[A-Za-z0-9_-]{8,}\b"
    ),
)


def sanitize_sensitive_text(value: Any) -> SensitiveTextResult:
    """Remove credential-like values while preserving useful context."""

    text = str(value or "")
    if not text:
        return SensitiveTextResult(
            text="",
            redacted=False,
            redaction_count=0,
        )

    count = 0

    def replace_private_key(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return PRIVATE_KEY_REDACTED

    text = _PRIVATE_KEY_RE.sub(
        replace_private_key,
        text,
    )

    def replace_authorization_header(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "Authorization: " + REDACTED

    text = _AUTHORIZATION_HEADER_RE.sub(
        replace_authorization_header,
        text,
    )

    def replace_named(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        label = match.group(1)
        separator = match.group(2)
        return f"{label}{separator}{REDACTED}"

    text = _NAMED_SECRET_RE.sub(
        replace_named,
        text,
    )

    def replace_bearer(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "Bearer " + REDACTED

    text = _BEARER_RE.sub(
        replace_bearer,
        text,
    )

    def replace_basic_auth(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return match.group(1) + REDACTED + match.group(3)

    text = _BASIC_AUTH_URL_RE.sub(
        replace_basic_auth,
        text,
    )

    def replace_email_pair(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return match.group(1) + REDACTED

    text = _EMAIL_SECRET_PAIR_RE.sub(
        replace_email_pair,
        text,
    )

    def replace_domain_user_secret(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return match.group(1) + REDACTED

    text = _DOMAIN_USER_SECRET_RE.sub(
        replace_domain_user_secret,
        text,
    )

    for pattern in _KNOWN_TOKEN_PATTERNS:
        text, replacements = pattern.subn(
            REDACTED,
            text,
        )
        count += replacements

    return SensitiveTextResult(
        text=text,
        redacted=count > 0,
        redaction_count=count,
    )


def sanitized_text(value: Any) -> str:
    return sanitize_sensitive_text(value).text


_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "passphrase",
    "secret",
    "secret_key",
    "client_secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "token",
}


def sanitize_sensitive_value(value: Any) -> Any:
    """Recursively sanitize serializable structures at persistence boundaries."""

    if isinstance(value, str):
        return sanitized_text(value)

    if isinstance(value, dict):
        result: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip().casefold()
            if normalized_key in _SENSITIVE_KEYS and item not in (None, "", False):
                result[key] = REDACTED
            else:
                result[key] = sanitize_sensitive_value(item)
        return result

    if isinstance(value, list):
        return [
            sanitize_sensitive_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            sanitize_sensitive_value(item)
            for item in value
        )

    return value


__all__ = [
    "PRIVATE_KEY_REDACTED",
    "REDACTED",
    "SensitiveTextResult",
    "sanitize_sensitive_text",
    "sanitize_sensitive_value",
    "sanitized_text",
]
