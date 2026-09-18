from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import re
from typing import Any

from app.intelligence_sources.contracts import (
    DataHandlingDecision,
    DataSensitivity,
)


_REDACTED = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    value: Any
    redacted_paths: tuple[str, ...] = ()

    @property
    def redacted_count(self) -> int:
        return len(self.redacted_paths)

    @property
    def changed(self) -> bool:
        return bool(self.redacted_paths)


class IntelligenceDataPolicy:
    """Central handling policy for source data sensitivity."""

    _DECISIONS = {
        DataSensitivity.PUBLIC: DataHandlingDecision(
            True, True, True, True, True, False,
            "Public information may be processed normally.",
        ),
        DataSensitivity.PUBLIC_SENSITIVE: DataHandlingDecision(
            True, True, True, True, True, False,
            "Public sensitive information remains subject to minimization.",
        ),
        DataSensitivity.BREACH_METADATA: DataHandlingDecision(
            True, True, True, True, True, False,
            "Breach metadata may be retained; embedded secrets must be redacted.",
        ),
        DataSensitivity.DARKWEB_PUBLIC: DataHandlingDecision(
            True, True, True, True, True, False,
            "Publicly accessible dark-web observations may be retained as evidence.",
        ),
        DataSensitivity.RESTRICTED: DataHandlingDecision(
            False, False, False, False, False, False,
            "Restricted data requires an explicitly authorized workspace.",
        ),
        DataSensitivity.SECRET_MATERIAL: DataHandlingDecision(
            True, False, False, False, False, True,
            "Secret material may be detected in memory but must not be persisted or exposed.",
        ),
        DataSensitivity.PROHIBITED: DataHandlingDecision(
            False, False, False, False, False, True,
            "Prohibited data must not be collected, persisted, analyzed, displayed or exported.",
        ),
    }

    def decision_for(
        self,
        sensitivity: DataSensitivity,
        *,
        restricted_authorized: bool = False,
    ) -> DataHandlingDecision:
        if (
            sensitivity is DataSensitivity.RESTRICTED
            and restricted_authorized
        ):
            return DataHandlingDecision(
                True,
                True,
                True,
                True,
                False,
                False,
                "Restricted data is allowed inside an explicitly authorized workspace; export stays disabled.",
            )
        return self._DECISIONS[sensitivity]


class IntelligenceDataSanitizer:
    """
    Recursive secret-material redactor.

    Safe indicators such as password_exposed=True remain visible, while actual
    passwords, tokens, cookies and private-key material are removed before
    search results or persistence can expose them.
    """

    REDACTED = _REDACTED

    _SAFE_INDICATORS = {
        "password_exposed",
        "password_hash_exposed",
        "credential_exposed",
        "credentials_exposed",
        "token_exposed",
        "session_exposed",
        "secret_material_present",
        "contains_credentials",
        "contains_secret_material",
    }

    _SECRET_KEYS = {
        "password",
        "passwd",
        "pwd",
        "plaintext_password",
        "password_value",
        "password_hash",
        "credential",
        "credential_value",
        "credential_hash",
        "token",
        "access_token",
        "refresh_token",
        "session_token",
        "session_id",
        "session_cookie",
        "cookie",
        "cookies",
        "authorization",
        "authorization_header",
        "auth_header",
        "api_key",
        "apikey",
        "client_secret",
        "secret",
        "secret_key",
        "private_key",
        "private_key_pem",
        "seed_phrase",
        "mnemonic",
        "recovery_phrase",
        "pin",
        "cvv",
        "cvc",
    }

    _SECRET_SUFFIXES = (
        "_password",
        "_passwd",
        "_token",
        "_session_cookie",
        "_api_key",
        "_client_secret",
        "_private_key",
        "_seed_phrase",
        "_recovery_phrase",
    )

    def sanitize(self, value: Any) -> SanitizationResult:
        redacted: list[str] = []
        sanitized = self._walk(value, path="$", redacted=redacted)
        return SanitizationResult(
            value=sanitized,
            redacted_paths=tuple(redacted),
        )

    def _walk(
        self,
        value: Any,
        *,
        path: str,
        redacted: list[str],
        field_name: str | None = None,
    ) -> Any:
        if field_name is not None and self._is_secret_key(field_name):
            redacted.append(path)
            return self.REDACTED

        if isinstance(value, dict):
            output = {}
            for key, child in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}"
                if self._is_secret_key(key_text):
                    output[key] = self.REDACTED
                    redacted.append(child_path)
                else:
                    output[key] = self._walk(
                        child,
                        path=child_path,
                        redacted=redacted,
                    )
            return output

        if isinstance(value, list):
            return [
                self._walk(
                    child,
                    path=f"{path}[{index}]",
                    redacted=redacted,
                )
                for index, child in enumerate(value)
            ]

        if isinstance(value, tuple):
            return tuple(
                self._walk(
                    child,
                    path=f"{path}[{index}]",
                    redacted=redacted,
                )
                for index, child in enumerate(value)
            )

        if is_dataclass(value) and not isinstance(value, type):
            changes = {}
            for item in fields(value):
                child = getattr(value, item.name)
                child_path = f"{path}.{item.name}"
                changes[item.name] = self._walk(
                    child,
                    path=child_path,
                    redacted=redacted,
                    field_name=item.name,
                )
            return replace(value, **changes)

        return value

    @classmethod
    def _normalize_key(cls, key: str) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "_",
            (key or "").strip().casefold(),
        ).strip("_")

    @classmethod
    def _is_secret_key(cls, key: str) -> bool:
        normalized = cls._normalize_key(key)

        if normalized in cls._SAFE_INDICATORS:
            return False

        if normalized in cls._SECRET_KEYS:
            return True

        return any(
            normalized.endswith(suffix)
            for suffix in cls._SECRET_SUFFIXES
        )
