from typing import Any
import httpx
import json

class GleifRegistryHttpClient:
    BASE_URL = "https://api.gleif.org/api/v1"

    def __init__(self, *, transport=None, user_agent: str = "OSINTXZ/1.0 RegistryIntelligence") -> None:
        self.transport = transport
        self.user_agent = user_agent

    def _client(self, timeout: int) -> httpx.Client:
        return httpx.Client(timeout=httpx.Timeout(float(timeout)), transport=self.transport, headers={"User-Agent": self.user_agent, "Accept": "application/vnd.api+json, application/json"})

    def get_record(self, lei: str, *, timeout: int = 30) -> dict[str, Any]:
        return self._get(f"{self.BASE_URL}/lei-records/{lei}", timeout=timeout)

    def _get(self, url: str, *, timeout: int, params=None) -> dict[str, Any]:
        max_bytes = 4_000_000
        with self._client(timeout) as client:
            with client.stream("GET", url, params=params, headers={"Accept-Encoding": "identity"}) as response:
                response.raise_for_status()
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected registry HTTP content encoding.")
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > max_bytes:
                        raise ValueError("Registry response exceeds download limit.")
                    body.extend(chunk)
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Registry response must be a JSON object.")
        return payload

    def search_records(self, value: str, *, country: str | None = None, limit: int = 20, timeout: int = 30) -> dict[str, Any]:
        params: dict[str, str | int] = {"filter[fulltext]": value, "page[size]": max(1, min(int(limit), 100))}
        if country:
            params["filter[entity.legalAddress.country]"] = country.strip().upper()
        return self._get(f"{self.BASE_URL}/lei-records", params=params, timeout=timeout)
