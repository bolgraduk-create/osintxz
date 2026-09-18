from __future__ import annotations

import json
from typing import Any

import httpx


class OpenCorporatesCredentialsError(RuntimeError):
    """Raised when the OpenCorporates API token is not configured."""


class OpenCorporatesHttpClient:
    """Bounded HTTP client for the OpenCorporates REST API."""

    BASE_URL = "https://api.opencorporates.com/v0.4"
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
            headers["X-API-TOKEN"] = self.api_token

        return httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=headers,
        )

    def search_companies(
        self,
        value: str,
        *,
        country: str | None = None,
        limit: int = 20,
        registration_id_only: bool = False,
        timeout: int = 30,
    ) -> dict[str, Any]:
        if not self.configured:
            raise OpenCorporatesCredentialsError(
                "OpenCorporates API token is not configured."
            )

        params: dict[str, str | int] = {
            "q": value.strip(),
            "per_page": max(1, min(int(limit), 100)),
            "page": 1,
            "order": "score",
        }

        if registration_id_only:
            params["fields"] = "company_number"
        else:
            params["normalise_company_name"] = "true"

        if country:
            params["country_code"] = country.strip().lower()

        return self._get(
            f"{self.BASE_URL}/companies/search",
            params=params,
            timeout=timeout,
        )

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None,
        timeout: int,
    ) -> dict[str, Any]:
        with self._client(timeout) as client:
            with client.stream(
                "GET",
                url,
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                content_encoding = response.headers.get(
                    "Content-Encoding",
                    "identity",
                ).lower()
                if content_encoding != "identity":
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
                "OpenCorporates response must be valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "OpenCorporates response must be a JSON object."
            )

        return payload
