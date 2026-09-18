from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.darkweb_intelligence.contracts import (
    DarkWebIndicator,
    DarkWebIndicatorKind,
)
from app.darkweb_intelligence.tor_client import TorOnionHttpClient


_EMAIL_RE = re.compile(
    r"(?i)(?<![a-z0-9._%+-])([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,63})(?![a-z0-9._%+-])"
)
_DOMAIN_RE = re.compile(
    r"(?i)\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})\b"
)
_USERNAME_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{3,32})\b")
_BTC_BECH32_RE = re.compile(r"\bbc1[ac-hj-np-z02-9]{25,62}\b", re.I)
_BTC_BASE58_RE = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
_ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_ONION_TEXT_RE = re.compile(
    r"(?i)https?://(?:[a-z0-9-]+\.)*[a-z2-7]{56}\.onion(?::\d+)?(?:/[^\s<>\"']*)?"
)
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|access[_-]?token|refresh[_-]?token|api[_-]?key|client[_-]?secret|session[_-]?cookie|secret)\s*[:=]\s*([^\s,;<>]{3,})"
)


def redact_inline_secrets(value: str | None) -> str | None:
    if value is None:
        return None
    return _INLINE_SECRET_RE.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        value,
    )


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lower = tag.casefold()
        if lower in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if lower == "title":
            self._in_title = True
        if lower == "a":
            for key, value in attrs:
                if key.casefold() == "href" and value:
                    self.links.append(str(value))
                    break

    def handle_endtag(self, tag: str) -> None:
        lower = tag.casefold()
        if lower in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if lower == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        self.text_parts.append(text)
        if self._in_title:
            self.title_parts.append(text)


class DarkWebIndicatorExtractor:
    """Extract bounded indicators without retaining the page body."""

    MAX_INDICATORS_PER_KIND = 100

    def extract(
        self,
        *,
        source_url: str,
        body: bytes,
        content_type: str,
    ) -> tuple[str | None, list[DarkWebIndicator]]:
        text = body.decode("utf-8", errors="replace")
        parser = _PageParser()
        links: list[str] = []

        if content_type in {"text/html", "application/xhtml+xml"}:
            parser.feed(text)
            visible_text = "\n".join(parser.text_parts)
            title = " ".join(parser.title_parts).strip() or None
            links = parser.links
        else:
            visible_text = text
            title = None

        title = redact_inline_secrets(title)
        indicators: list[DarkWebIndicator] = []
        seen: set[tuple[DarkWebIndicatorKind, str]] = set()
        counts: dict[DarkWebIndicatorKind, int] = {}

        def add(kind: DarkWebIndicatorKind, value: str, confidence: float = 0.8) -> None:
            cleaned = value.strip()
            key = (kind, cleaned.casefold())
            if not cleaned or key in seen:
                return
            if counts.get(kind, 0) >= self.MAX_INDICATORS_PER_KIND:
                return
            seen.add(key)
            counts[kind] = counts.get(kind, 0) + 1
            indicators.append(DarkWebIndicator(kind, cleaned, confidence))

        for match in _EMAIL_RE.finditer(visible_text):
            add(DarkWebIndicatorKind.EMAIL, match.group(1), 0.95)

        for match in _USERNAME_RE.finditer(visible_text):
            add(DarkWebIndicatorKind.USERNAME, match.group(1), 0.75)

        for match in _BTC_BECH32_RE.finditer(visible_text):
            add(DarkWebIndicatorKind.BITCOIN_ADDRESS, match.group(0), 0.9)
        for match in _BTC_BASE58_RE.finditer(visible_text):
            add(DarkWebIndicatorKind.BITCOIN_ADDRESS, match.group(0), 0.85)
        for match in _ETH_RE.finditer(visible_text):
            add(DarkWebIndicatorKind.ETHEREUM_ADDRESS, match.group(0), 0.9)

        for match in _ONION_TEXT_RE.finditer(visible_text):
            normalized = self._normalize_link(source_url, match.group(0))
            if normalized and normalized.endswith(".onion"):
                add(DarkWebIndicatorKind.ONION_URL, normalized, 0.9)
            elif normalized and ".onion/" in normalized:
                add(DarkWebIndicatorKind.ONION_URL, normalized, 0.9)

        for raw in links:
            normalized = self._normalize_link(source_url, raw)
            if not normalized:
                continue
            hostname = (urlsplit(normalized).hostname or "").casefold()
            if hostname.endswith(".onion"):
                add(DarkWebIndicatorKind.ONION_URL, normalized, 0.9)
            else:
                add(DarkWebIndicatorKind.CLEARNET_URL, normalized, 0.8)
                if hostname:
                    add(DarkWebIndicatorKind.DOMAIN, hostname, 0.9)

        # Domains mentioned in visible text. Exclude onion pseudo-TLDs.
        for match in _DOMAIN_RE.finditer(visible_text):
            domain = match.group(1).casefold()
            if not domain.endswith(".onion"):
                add(DarkWebIndicatorKind.DOMAIN, domain, 0.8)

        return title, indicators

    @staticmethod
    def _normalize_link(base_url: str, raw: str) -> str | None:
        try:
            absolute = urljoin(base_url, raw.strip())
            parsed = urlsplit(absolute)
            if parsed.scheme not in {"http", "https"}:
                return None
            if parsed.username or parsed.password:
                return None
            hostname = (parsed.hostname or "").casefold().rstrip(".")
            if not hostname:
                return None
            netloc = hostname
            if parsed.port is not None:
                netloc += f":{parsed.port}"
            normalized = urlunsplit(
                (parsed.scheme, netloc, parsed.path or "/", "", "")
            )
            if hostname.endswith(".onion"):
                TorOnionHttpClient.validate_onion_url(normalized)
            return normalized
        except (ValueError, TypeError):
            return None
