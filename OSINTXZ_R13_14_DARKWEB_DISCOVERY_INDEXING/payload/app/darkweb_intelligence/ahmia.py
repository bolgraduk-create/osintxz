from __future__ import annotations

import hashlib
import re
import time
from urllib.parse import urlsplit

import httpx


_ONION_RE = re.compile(r"(?i)\b([a-z2-7]{56}\.onion)\b")
_MD5_RE = re.compile(r"(?i)\b([a-f0-9]{32})\b")


class AhmiaDirectoryError(RuntimeError):
    pass


class AhmiaDirectoryClient:
    """Read-only Ahmia metadata client.

    It never proxies through Tor and never fetches onion content. It only reads
    Ahmia's public clearnet directory/blocklist metadata so the Tor crawler can
    seed or reject public onion addresses safely.
    """

    DEFAULT_DIRECTORY_URL = "https://www.ahmia.fi/onions/"
    DEFAULT_BLACKLIST_URL = "https://www.ahmia.fi/blacklist/banned/"
    MAX_DIRECTORY_BYTES = 8_000_000
    MAX_BLACKLIST_BYTES = 8_000_000

    def __init__(
        self,
        *,
        directory_url: str | None = None,
        blacklist_url: str | None = None,
        transport=None,
        cache_ttl_seconds: int = 86400,
        user_agent: str = "OSINTXZ/1.0 DarkWebDiscovery",
    ) -> None:
        self.directory_url = (directory_url or self.DEFAULT_DIRECTORY_URL).strip()
        self.blacklist_url = (blacklist_url or self.DEFAULT_BLACKLIST_URL).strip()
        self.transport = transport
        self.cache_ttl_seconds = max(int(cache_ttl_seconds), 60)
        self.user_agent = user_agent
        self._blacklist_cache: frozenset[str] | None = None
        self._blacklist_cached_at: float = 0.0

    def list_known_onions(self, *, limit: int = 1000, timeout: int = 30) -> tuple[str, ...]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be 1..10000.")
        text = self._get_text(self.directory_url, timeout=timeout, max_bytes=self.MAX_DIRECTORY_BYTES)
        out: list[str] = []
        seen: set[str] = set()
        for match in _ONION_RE.finditer(text):
            host = match.group(1).casefold()
            if host in seen:
                continue
            seen.add(host)
            out.append(f"http://{host}/")
            if len(out) >= limit:
                break
        return tuple(out)

    def blacklist_hashes(self, *, timeout: int = 30, force_refresh: bool = False) -> frozenset[str]:
        now = time.monotonic()
        if (
            not force_refresh
            and self._blacklist_cache is not None
            and now - self._blacklist_cached_at < self.cache_ttl_seconds
        ):
            return self._blacklist_cache

        text = self._get_text(self.blacklist_url, timeout=timeout, max_bytes=self.MAX_BLACKLIST_BYTES)
        hashes = frozenset(match.group(1).casefold() for match in _MD5_RE.finditer(text))
        if not hashes:
            raise AhmiaDirectoryError("Ahmia blacklist response did not contain any hashes.")
        self._blacklist_cache = hashes
        self._blacklist_cached_at = now
        return hashes

    def is_blocked(self, onion_url: str, *, hashes: frozenset[str] | None = None, timeout: int = 30) -> bool:
        host = (urlsplit(onion_url).hostname or onion_url).casefold().rstrip(".")
        if not _ONION_RE.fullmatch(host):
            raise ValueError("Expected a v3 .onion hostname or URL.")
        digest = hashlib.md5(host.encode("utf-8")).hexdigest()  # Ahmia's published compatibility format.
        values = hashes if hashes is not None else self.blacklist_hashes(timeout=timeout)
        return digest in values

    def _get_text(self, url: str, *, timeout: int, max_bytes: int) -> str:
        headers = {"User-Agent": self.user_agent, "Accept": "text/plain,text/html;q=0.9"}
        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(timeout)),
                transport=self.transport,
                headers=headers,
                follow_redirects=False,
            ) as client:
                with client.stream("GET", url, headers={"Accept-Encoding": "identity"}) as response:
                    if 300 <= response.status_code < 400:
                        raise AhmiaDirectoryError("Ahmia metadata redirect was not followed automatically.")
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        if len(body) + len(chunk) > max_bytes:
                            raise AhmiaDirectoryError("Ahmia metadata response exceeds download limit.")
                        body.extend(chunk)
        except httpx.HTTPError as exc:
            raise AhmiaDirectoryError(str(exc)) from exc
        return body.decode("utf-8", errors="replace")
