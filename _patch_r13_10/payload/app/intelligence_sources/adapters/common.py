from __future__ import annotations

import json
from typing import Any

import httpx


class JsonHttpClient:
    MAX_BYTES = 4_000_000

    def __init__(
        self,
        *,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 RemoteAdapters",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self.headers = dict(headers or {})

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request_json(
            "GET", url, params=params, timeout=timeout, headers=headers
        )

    def post_json(
        self,
        url: str,
        *,
        json_body: dict[str, Any],
        params: dict[str, str | int] | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request_json(
            "POST",
            url,
            params=params,
            json_body=json_body,
            timeout=timeout,
            headers=headers,
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            **self.headers,
            **dict(headers or {}),
        }
        if json_body is not None:
            request_headers.setdefault("Content-Type", "application/json")

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers=request_headers,
            follow_redirects=False,
        ) as client:
            with client.stream(
                method,
                url,
                params=params,
                json=json_body,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_BYTES:
                        raise ValueError("Remote source response exceeds limit.")
                    body.extend(chunk)
                response.raise_for_status()

        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Remote source response must be JSON.") from exc
