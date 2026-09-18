from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx


_ONION_V3_RE = re.compile(r"^[a-z2-7]{56}$")
_SENSITIVE_QUERY_KEYS = {
    "password", "passwd", "pwd", "token", "access_token", "refresh_token",
    "session", "session_id", "cookie", "api_key", "apikey", "secret",
    "client_secret", "private_key",
}


class TorConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FetchedOnionPage:
    url: str
    status_code: int
    content_type: str
    body: bytes
    location: str | None = None


class TorOnionHttpClient:
    """Bounded GET-only client for public v3 onion pages."""

    MAX_RESPONSE_BYTES = 2_000_000
    ALLOWED_CONTENT_TYPES = (
        "text/html",
        "text/plain",
        "application/xhtml+xml",
    )

    def __init__(
        self,
        *,
        proxy_url: str = "socks5h://127.0.0.1:9050",
        transport=None,
        user_agent: str = "OSINTXZ/1.0 DarkWebIntelligence",
    ) -> None:
        self.proxy_url = self._validate_proxy_url(proxy_url)
        self.transport = transport
        self.user_agent = user_agent

    @staticmethod
    def _validate_proxy_url(value: str) -> str:
        parsed = urlsplit((value or "").strip())
        if parsed.scheme not in {"socks5", "socks5h"}:
            raise TorConfigurationError(
                "Tor proxy must use socks5:// or socks5h://."
            )
        host = (parsed.hostname or "").casefold()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise TorConfigurationError(
                "R13.7 accepts only a local Tor SOCKS proxy."
            )
        if parsed.username or parsed.password:
            raise TorConfigurationError(
                "Proxy credentials are not supported by R13.7."
            )
        if parsed.port is None:
            raise TorConfigurationError("Tor proxy URL must include a port.")
        return value.strip()

    @staticmethod
    def validate_onion_url(value: str) -> str:
        parsed = urlsplit((value or "").strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http/https onion URLs are supported.")
        if parsed.username or parsed.password:
            raise ValueError("Credentials in onion URLs are prohibited.")
        hostname = (parsed.hostname or "").casefold().rstrip(".")
        labels = hostname.split(".")
        if len(labels) < 2 or labels[-1] != "onion":
            raise ValueError("Target must be a .onion service.")
        if not _ONION_V3_RE.fullmatch(labels[-2]):
            raise ValueError("Only Tor v3 56-character onion addresses are supported.")

        for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
            normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
            if normalized in _SENSITIVE_QUERY_KEYS:
                raise ValueError(
                    "Sensitive credential-like URL query parameters are prohibited."
                )

        netloc = hostname
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        return urlunsplit(
            (parsed.scheme, netloc, parsed.path or "/", parsed.query, "")
        )

    def fetch(
        self,
        url: str,
        *,
        timeout: int = 30,
        max_bytes: int | None = None,
    ) -> FetchedOnionPage:
        target = self.validate_onion_url(url)
        limit = min(
            max_bytes or self.MAX_RESPONSE_BYTES,
            self.MAX_RESPONSE_BYTES,
        )
        if limit < 1:
            raise ValueError("max_bytes must be positive.")

        client_kwargs = dict(
            timeout=httpx.Timeout(float(timeout)),
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,text/plain,application/xhtml+xml",
            },
            follow_redirects=False,
            trust_env=False,
        )
        if self.transport is None:
            client_kwargs["proxy"] = self.proxy_url
        else:
            client_kwargs["transport"] = self.transport

        with httpx.Client(**client_kwargs) as client:
            with client.stream(
                "GET",
                target,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                encoding = response.headers.get(
                    "Content-Encoding", "identity"
                ).casefold()
                if encoding != "identity":
                    raise ValueError("Unexpected onion response content encoding.")

                content_type = response.headers.get(
                    "Content-Type", "text/plain"
                ).split(";", 1)[0].strip().casefold()
                disposition = response.headers.get(
                    "Content-Disposition", ""
                ).casefold()

                if "attachment" in disposition:
                    raise ValueError("Onion file attachments are not downloaded.")
                if content_type not in self.ALLOWED_CONTENT_TYPES:
                    raise ValueError(
                        f"Unsupported onion content type: {content_type or 'unknown'}."
                    )

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > limit:
                        raise ValueError("Onion page exceeds download limit.")
                    body.extend(chunk)

                return FetchedOnionPage(
                    url=target,
                    status_code=response.status_code,
                    content_type=content_type,
                    body=bytes(body),
                    location=response.headers.get("Location"),
                )
