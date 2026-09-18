from __future__ import annotations

import json
from typing import Any

import httpx


class CourtListenerCredentialsError(RuntimeError):
    """Raised when CourtListener automatic API access is not configured."""


class CourtListenerHttpClient:
    """Bounded HTTP client for CourtListener Legal Search API v4."""

    BASE_URL = "https://www.courtlistener.com"
    SEARCH_URL = f"{BASE_URL}/api/rest/v4/search/"
    MAX_RESPONSE_BYTES = 4_000_000

    def __init__(
        self,
        *,
        api_token: str | None = None,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 RegistryIntelligence",
    ) -> None:
        self.api_token = (api_token or "").strip() or None
        self.transport = transport
        self.user_agent = user_agent

    @property
    def configured(self) -> bool:
        return self.api_token is not None

    def _client(self, timeout: int) -> httpx.Client:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Token {self.api_token}"
        return httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
            follow_redirects=False,
        )

    def search_case_law(
        self,
        value: str,
        *,
        field: str,
        limit: int = 20,
        timeout: int = 30,
    ) -> dict[str, Any]:
        if not self.configured:
            raise CourtListenerCredentialsError(
                "CourtListener API token is not configured."
            )
        if field not in {"caseName", "docketNumber"}:
            raise ValueError("Unsupported CourtListener search field.")

        query_value = self._quoted_search_value(value)
        params: dict[str, str | int] = {
            "type": "o",
            "q": f'{field}:"{query_value}"',
        }

        # v4 search uses cursor pagination and does not expose a stable
        # per-page contract we should depend on here. We bound locally after
        # one response instead of following pagination automatically.
        payload = self._get(
            self.SEARCH_URL,
            params=params,
            timeout=timeout,
        )
        results = payload.get("results")
        if isinstance(results, list) and len(results) > max(1, int(limit)):
            payload = dict(payload)
            payload["results"] = results[: max(1, int(limit))]
        return payload

    @staticmethod
    def _quoted_search_value(value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("CourtListener search value must not be empty.")
        # Escape only characters that would break the quoted field expression.
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        timeout: int,
    ) -> dict[str, Any]:
        with self._client(timeout) as client:
            with client.stream(
                "GET",
                url,
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if 300 <= response.status_code < 400:
                    raise ValueError(
                        "Unexpected redirect from CourtListener API."
                    )
                if response.headers.get(
                    "Content-Encoding", "identity"
                ).lower() != "identity":
                    raise ValueError(
                        "Unexpected registry HTTP content encoding."
                    )

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_RESPONSE_BYTES:
                        raise ValueError(
                            "Registry response exceeds download limit."
                        )
                    body.extend(chunk)
                response.raise_for_status()

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(
                "CourtListener response must be valid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(
                "CourtListener response must be a JSON object."
            )
        return payload
