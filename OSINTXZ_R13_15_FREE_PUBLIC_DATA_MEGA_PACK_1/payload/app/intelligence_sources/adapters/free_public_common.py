from __future__ import annotations

import json
from typing import Any

import httpx

from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
)


class PublicDataResponseError(ValueError):
    pass


class PublicJsonClient:
    """Small bounded JSON client for free/public-data adapters."""

    MAX_BYTES = 8_000_000

    def __init__(
        self,
        *,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 FreePublicData",
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self.extra_headers = dict(extra_headers or {})

    def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> Any:
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            **self.extra_headers,
            **(headers or {}),
        }
        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            follow_redirects=False,
            headers=request_headers,
        ) as client:
            response = client.request(
                method.upper(),
                url,
                params=params,
                json=json_body,
            )
            limit = int(max_bytes or self.MAX_BYTES)
            if len(response.content) > limit:
                raise PublicDataResponseError(
                    f"Public-data response exceeds {limit} bytes."
                )
            response.raise_for_status()

        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PublicDataResponseError(
                "Public-data response must be valid JSON."
            ) from exc


def failure_result(source: str, exc: Exception) -> RemoteAdapterResult:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        retryable = code == 429 or code >= 500
        return RemoteAdapterResult(
            source=source,
            status=(
                RemoteAdapterStatus.PARTIAL
                if retryable
                else RemoteAdapterStatus.FAILED
            ),
            error=f"HTTP {code}.",
            metadata={
                "retryable": retryable,
                "rate_limited": code == 429,
                "failure_isolated": True,
            },
        )
    if isinstance(exc, httpx.RequestError):
        return RemoteAdapterResult(
            source=source,
            status=RemoteAdapterStatus.PARTIAL,
            error=str(exc),
            metadata={
                "retryable": True,
                "failure_isolated": True,
            },
        )
    return RemoteAdapterResult(
        source=source,
        status=RemoteAdapterStatus.FAILED,
        error=str(exc),
        metadata={"failure_isolated": True},
    )


def first_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        for item in value:
            text = first_text(item)
            if text:
                return text
    return None


def text_list(value: Any, *, limit: int = 20) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out
