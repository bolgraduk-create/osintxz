from __future__ import annotations

import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

try:
    import truststore
except ImportError:
    truststore = None

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebDocument,
    OpenWebProviderInfo,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider


class _VisibleTextParser(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        name = tag.casefold()
        if name in self._SKIP:
            self._skip_depth += 1
        if name == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if name in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
        if name == "title":
            self._in_title = False
            value = " ".join(self._title_parts).strip()
            self.title = value or None

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        value = " ".join(data.split())
        if not value:
            return
        self._parts.append(value)
        if self._in_title:
            self._title_parts.append(value)

    @property
    def text(self) -> str:
        return "\n".join(self._parts)


class LiveWebOpenWebProvider(OpenWebProvider):
    """
    Passive fetch of one public HTTP(S) page.

    This provider does not crawl links, bypass access controls, execute
    JavaScript, submit forms, or authenticate. Every redirect destination is
    revalidated to block requests into private/local networks.
    """

    def __init__(
        self,
        *,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 LiveWebProvider",
        max_response_bytes: int = 2_000_000,
        max_redirects: int = 5,
    ) -> None:
        self.transport = transport
        self.user_agent = user_agent
        self.max_response_bytes = max(
            64_000,
            min(int(max_response_bytes), 5_000_000),
        )
        self.max_redirects = max(0, min(int(max_redirects), 8))
        self._info = OpenWebProviderInfo(
            name="live_web",
            display_name="Live Web",
            supported_targets=frozenset({OsintTargetType.URL}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=5,
        )

    @property
    def info(self) -> OpenWebProviderInfo:
        return self._info

    def search(self, query: OpenWebQuery) -> OpenWebResult:
        if not self.supports(query):
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_SUPPORTED,
                error="URL only.",
            )

        try:
            document = self._fetch(query.value, timeout=query.timeout)
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=str(exc) or exc.__class__.__name__,
                metadata={
                    "failure_isolated": True,
                    "passive": True,
                    "public_data_only": True,
                },
            )

        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.SUCCESS,
            documents=[document] if document is not None else [],
            metadata={
                "query_strategy": "single_public_url_fetch",
                "records_returned": 1 if document is not None else 0,
                "passive": True,
                "public_data_only": True,
                "javascript_executed": False,
                "link_crawl": False,
            },
        )

    def _fetch(self, value: str, *, timeout: int) -> OpenWebDocument | None:
        current = value.strip()
        redirects = 0

        while True:
            self._validate_public_url(current)

            with httpx.Client(
                timeout=httpx.Timeout(float(timeout)),
                follow_redirects=False,
                transport=self.transport,
                verify=self._tls_context(),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.1",
                },
            ) as client:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if not location:
                            response.raise_for_status()
                        redirects += 1
                        if redirects > self.max_redirects:
                            raise RuntimeError("Live Web redirect limit exceeded.")
                        current = urljoin(current, location)
                        continue

                    if response.status_code == 404:
                        return None

                    response.raise_for_status()

                    content_type = (
                        response.headers.get("Content-Type", "")
                        .split(";", 1)[0]
                        .strip()
                        .casefold()
                    )

                    allowed = (
                        content_type.startswith("text/")
                        or content_type in {
                            "application/xhtml+xml",
                            "application/xml",
                        }
                    )
                    if content_type and not allowed:
                        raise ValueError(
                            f"Unsupported Live Web content type: {content_type}"
                        )

                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > self.max_response_bytes:
                            raise ValueError(
                                "Live Web response exceeded bounded-size limit."
                            )

                    encoding = response.encoding or "utf-8"
                    raw_text = bytes(body).decode(
                        encoding,
                        errors="replace",
                    )

                    final_url = str(response.url)
                    self._validate_public_url(final_url)

            title = None
            visible = raw_text

            if (
                "html" in content_type
                or "<html" in raw_text[:1000].casefold()
            ):
                parser = _VisibleTextParser()
                parser.feed(raw_text)
                visible = parser.text
                title = parser.title

            visible = visible.strip()
            if not visible:
                return None

            return OpenWebDocument(
                url=final_url,
                provider=self.info.name,
                title=title,
                text=visible,
                content_type=content_type or None,
                confidence=0.90,
                reliability=0.85,
                metadata={
                    "live_fetch": True,
                    "original_url": value.strip(),
                    "final_url": final_url,
                    "redirect_count": redirects,
                    "response_bytes": len(body),
                    "javascript_executed": False,
                    "link_crawl": False,
                    "public_data_only": True,
                },
            )

    @staticmethod
    def _tls_context() -> ssl.SSLContext:
        # Prefer the operating-system trust store on Windows so HTTPS trust
        # decisions match the machine/browser policy. TLS verification stays
        # enabled; this is deliberately not equivalent to verify=False.
        if truststore is not None:
            return truststore.SSLContext(
                ssl.PROTOCOL_TLS_CLIENT
            )

        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        return context

    @classmethod
    def _validate_public_url(cls, value: str) -> None:
        parsed = urlsplit(value.strip())

        if parsed.scheme.casefold() not in {"http", "https"}:
            raise ValueError("Live Web only permits http/https URLs.")

        host = (parsed.hostname or "").strip().rstrip(".")
        if not host:
            raise ValueError("Live Web URL must contain a hostname.")

        lowered = host.casefold()
        if lowered == "localhost" or lowered.endswith(".localhost"):
            raise ValueError("Localhost targets are not permitted.")

        addresses: set[str] = set()

        try:
            addresses.add(str(ipaddress.ip_address(host)))
        except ValueError:
            try:
                infos = socket.getaddrinfo(
                    host,
                    parsed.port or (443 if parsed.scheme.casefold() == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            except socket.gaierror as exc:
                raise ValueError(
                    f"Live Web hostname could not be resolved: {host}"
                ) from exc

            for info in infos:
                address = info[4][0]
                if address:
                    addresses.add(address)

        if not addresses:
            raise ValueError("Live Web hostname resolved to no addresses.")

        for raw in addresses:
            ip = ipaddress.ip_address(raw)
            if not ip.is_global:
                raise ValueError(
                    "Private, local, link-local, reserved, or otherwise "
                    "non-global network targets are not permitted."
                )
