"""HTTP client for the central OSINTXZ Registry Backend."""
from __future__ import annotations

from urllib.parse import quote, urlsplit

import httpx

from app.registry_intelligence.contracts import RegistryProviderResult, RegistryQuery
from app.registry_intelligence.transport import (
    registry_provider_result_from_wire,
    registry_query_to_wire,
)


class RegistryApiClientError(RuntimeError):
    pass


class RegistryApiHttpClient:
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(
        self,
        *,
        base_url: str,
        token: str | None = None,
        default_timeout: int = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized_url = (base_url or "").strip().rstrip("/")
        self._validate_base_url(normalized_url)
        self.base_url = normalized_url
        self.token = (token or "").strip() or None
        self.default_timeout = max(1, min(int(default_timeout), 60))
        self._client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers={"User-Agent": "OSINTXZ/RegistryClient"},
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> dict:
        try:
            response = self._client.get(
                "/health",
                timeout=self.default_timeout,
            )
            self._raise_for_response(response)
            payload = response.json()
            if not isinstance(payload, dict):
                raise RegistryApiClientError("Malformed Registry Backend health response.")
            return payload
        except RegistryApiClientError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise RegistryApiClientError(f"Registry Backend health request failed: {exc}") from exc

    def search_provider(
        self,
        *,
        provider: str,
        query: RegistryQuery,
    ) -> RegistryProviderResult:
        provider_name = (provider or "").strip().casefold()
        if not provider_name:
            raise RegistryApiClientError("Registry provider name is required.")

        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request_timeout = max(1, min(int(query.timeout), self.default_timeout, 60))
        path = f"/v1/providers/{quote(provider_name, safe='')}/search"

        try:
            response = self._client.post(
                path,
                json=registry_query_to_wire(query),
                headers=headers,
                timeout=request_timeout,
            )
            self._raise_for_response(response)
            payload = response.json()
            if not isinstance(payload, dict):
                raise RegistryApiClientError("Malformed Registry Backend response.")
            result = registry_provider_result_from_wire(payload)
        except RegistryApiClientError:
            raise
        except httpx.TimeoutException as exc:
            raise RegistryApiClientError("Registry Backend request timed out.") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise RegistryApiClientError(f"Registry Backend request failed: {exc}") from exc

        if result.provider != provider_name:
            raise RegistryApiClientError(
                "Registry Backend returned a result for a different provider."
            )
        return result

    def _raise_for_response(self, response: httpx.Response) -> None:
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.MAX_RESPONSE_BYTES:
                    raise RegistryApiClientError("Registry Backend response is too large.")
            except ValueError:
                pass
        if len(response.content) > self.MAX_RESPONSE_BYTES:
            raise RegistryApiClientError("Registry Backend response is too large.")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("detail") or "").strip()
            except ValueError:
                detail = ""
            suffix = f": {detail}" if detail else ""
            raise RegistryApiClientError(
                f"Registry Backend returned HTTP {response.status_code}{suffix}"
            ) from exc

    @staticmethod
    def _validate_base_url(url: str) -> None:
        if not url:
            raise ValueError("registry_api_url must not be empty.")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("registry_api_url must be an absolute HTTP(S) URL.")
        if parsed.username or parsed.password:
            raise ValueError("registry_api_url must not contain embedded credentials.")
        if parsed.query or parsed.fragment:
            raise ValueError("registry_api_url must not contain query or fragment components.")
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme == "http" and parsed.hostname.casefold() not in local_hosts:
            raise ValueError("Remote Registry Backend connections must use HTTPS.")
