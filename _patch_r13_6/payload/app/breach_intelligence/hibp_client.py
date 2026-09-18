from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import quote

import httpx


class HibpCredentialsError(RuntimeError):
    pass


class HibpHttpClient:
    """Minimal bounded HIBP v3 + Pwned Passwords client."""

    API_BASE_URL = "https://haveibeenpwned.com/api/v3"
    PASSWORDS_BASE_URL = "https://api.pwnedpasswords.com"
    MAX_JSON_BYTES = 4_000_000
    MAX_RANGE_BYTES = 2_000_000

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport=None,
        passwords_transport=None,
        user_agent: str = "OSINTXZ/1.0 BreachIntelligence",
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.transport = transport
        self.passwords_transport = (
            passwords_transport
            if passwords_transport is not None
            else transport
        )
        self.user_agent = user_agent

    @property
    def account_lookup_configured(self) -> bool:
        return self.api_key is not None

    def breached_account(
        self,
        email: str,
        *,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        if not self.api_key:
            raise HibpCredentialsError(
                "HIBP API key is not configured for breached-account lookup."
            )

        value = email.strip()
        if not value or "@" not in value:
            raise ValueError("Malformed email address.")

        url = (
            f"{self.API_BASE_URL}/breachedaccount/"
            f"{quote(value, safe='')}"
        )
        payload = self._json_get(
            url,
            params={"truncateResponse": "false"},
            timeout=timeout,
            api_key=self.api_key,
        )
        if not isinstance(payload, list):
            raise ValueError("HIBP breached-account response must be a JSON list.")

        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    def pwned_password_count(
        self,
        password: str,
        *,
        timeout: int = 30,
    ) -> int:
        if not isinstance(password, str) or not password:
            raise ValueError("Password must not be empty.")

        digest = hashlib.sha1(
            password.encode("utf-8")
        ).hexdigest().upper()
        prefix = digest[:5]
        suffix = digest[5:]

        url = f"{self.PASSWORDS_BASE_URL}/range/{prefix}"

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.passwords_transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/plain",
                "Add-Padding": "true",
            },
        ) as client:
            with client.stream(
                "GET",
                url,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if response.headers.get(
                    "Content-Encoding", "identity"
                ).lower() != "identity":
                    raise ValueError(
                        "Unexpected Pwned Passwords content encoding."
                    )

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_RANGE_BYTES:
                        raise ValueError(
                            "Pwned Passwords response exceeds download limit."
                        )
                    body.extend(chunk)

                response.raise_for_status()

        text = body.decode("utf-8", errors="strict")
        for line in text.splitlines():
            candidate, sep, count_text = line.partition(":")
            if not sep:
                continue
            if candidate.strip().upper() != suffix:
                continue
            try:
                count = int(count_text.strip())
            except ValueError:
                raise ValueError(
                    "Malformed Pwned Passwords prevalence count."
                )
            return max(count, 0)

        return 0

    def _json_get(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
        timeout: int,
        api_key: str | None,
    ) -> Any:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if api_key:
            headers["hibp-api-key"] = api_key

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
        ) as client:
            with client.stream(
                "GET",
                url,
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if response.headers.get(
                    "Content-Encoding", "identity"
                ).lower() != "identity":
                    raise ValueError(
                        "Unexpected HIBP content encoding."
                    )

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_JSON_BYTES:
                        raise ValueError(
                            "HIBP response exceeds download limit."
                        )
                    body.extend(chunk)

                response.raise_for_status()

        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("HIBP response must be valid JSON.") from exc
