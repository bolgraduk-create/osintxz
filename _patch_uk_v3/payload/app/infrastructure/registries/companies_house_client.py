from __future__ import annotations

import json
from typing import Any

import httpx


class CompaniesHouseCredentialsError(RuntimeError):
    """Raised when the Companies House API key is not configured."""


class CompaniesHouseHttpClient:
    """Bounded client for the official Companies House Public Data API."""

    BASE_URL = "https://api.company-information.service.gov.uk"
    MAX_RESPONSE_BYTES = 4_000_000

    def __init__(
        self,
        *,
        api_key: str | None = None,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 RegistryIntelligence",
    ) -> None:
        self.api_key = (api_key or "").strip() or None
        self.transport = transport
        self.user_agent = user_agent

    @property
    def configured(self) -> bool:
        return self.api_key is not None

    def _client(self, timeout: int) -> httpx.Client:
        if not self.configured:
            raise CompaniesHouseCredentialsError(
                "Companies House API key is not configured."
            )

        return httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            auth=httpx.BasicAuth(self.api_key or "", ""),
        )

    def get_company_profile(
        self,
        company_number: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        number = company_number.strip().upper()
        return self._get(
            f"{self.BASE_URL}/company/{number}",
            timeout=timeout,
        )

    def search_companies(
        self,
        value: str,
        *,
        limit: int = 20,
        timeout: int = 30,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "q": value.strip(),
            "items_per_page": max(1, min(int(limit), 100)),
            "start_index": 0,
        }
        return self._get(
            f"{self.BASE_URL}/search/companies",
            params=params,
            timeout=timeout,
        )

    def _get(
        self,
        url: str,
        *,
        timeout: int,
        params: dict[str, str | int] | None = None,
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
                "Companies House response must be valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "Companies House response must be a JSON object."
            )
        return payload
