from __future__ import annotations

from collections import deque
from urllib.parse import urlsplit, urlunsplit

from app.darkweb_intelligence.ahmia import AhmiaDirectoryClient, AhmiaDirectoryError
from app.darkweb_intelligence.contracts import DarkWebFetchStatus, DarkWebIndicatorKind
from app.darkweb_intelligence.discovery_contracts import (
    OnionDiscoveryPage,
    OnionDiscoveryRequest,
    OnionDiscoveryResult,
    OnionDiscoveryStatus,
)
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.darkweb_intelligence.tor_client import TorOnionHttpClient


_FETCH_STATUS = {
    DarkWebFetchStatus.SUCCESS: OnionDiscoveryStatus.SUCCESS,
    DarkWebFetchStatus.PARTIAL: OnionDiscoveryStatus.PARTIAL,
    DarkWebFetchStatus.BLOCKED: OnionDiscoveryStatus.BLOCKED,
    DarkWebFetchStatus.NOT_CONFIGURED: OnionDiscoveryStatus.NOT_CONFIGURED,
    DarkWebFetchStatus.FAILED: OnionDiscoveryStatus.FAILED,
}


class DarkWebDiscoveryService:
    """Bounded, read-only public onion discovery.

    The service only performs GET requests through the already-restricted
    TorOnionHttpClient. It never authenticates, posts forms, follows redirects,
    downloads attachments, executes scripts, or stores page bodies.
    """

    def __init__(
        self,
        *,
        page_service: DarkWebIntelligenceService,
        ahmia_client: AhmiaDirectoryClient | None = None,
    ) -> None:
        self.page_service = page_service
        self.ahmia_client = ahmia_client or AhmiaDirectoryClient()

    def directory_candidates(self, *, limit: int = 250, timeout: int = 30) -> tuple[str, ...]:
        """Return known non-banned Ahmia onion URLs as candidates only.

        No onion URL is fetched by this method.
        """
        return self.ahmia_client.list_known_onions(limit=limit, timeout=timeout)

    def discover(self, request: OnionDiscoveryRequest) -> OnionDiscoveryResult:
        seeds = tuple(self._canonicalize(item) for item in request.seeds)

        blacklist: frozenset[str] | None = None
        blacklist_available = False
        try:
            blacklist = self.ahmia_client.blacklist_hashes(timeout=request.timeout)
            blacklist_available = True
        except (AhmiaDirectoryError, ValueError) as exc:
            if request.require_ahmia_blocklist:
                return OnionDiscoveryResult(
                    request=request,
                    status=OnionDiscoveryStatus.NOT_CONFIGURED,
                    errors=[f"Ahmia safety blocklist unavailable: {exc}"],
                    metadata={
                        "ahmia_blocklist_checked": False,
                        "tor_requests_started": False,
                        "fail_closed": True,
                    },
                )

        queue = deque((seed, 0) for seed in seeds)
        queued = set(seeds)
        visited: set[str] = set()
        host_counts: dict[str, int] = {}
        discovered: list[str] = list(seeds)
        blocked: list[str] = []
        pages: list[OnionDiscoveryPage] = []
        errors: list[str] = []

        while queue and len(pages) < request.max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            host = (urlsplit(url).hostname or "").casefold()
            if host_counts.get(host, 0) >= request.per_host_limit:
                continue

            if blacklist is not None and self.ahmia_client.is_blocked(url, hashes=blacklist):
                blocked.append(url)
                pages.append(
                    OnionDiscoveryPage(
                        url=url,
                        depth=depth,
                        status=OnionDiscoveryStatus.BLOCKED,
                        error="Blocked by Ahmia safety hashlist before Tor fetch.",
                        metadata={"ahmia_blocklist_match": True, "tor_fetch_attempted": False},
                    )
                )
                continue

            host_counts[host] = host_counts.get(host, 0) + 1
            result = self.page_service.fetch_public_onion(url, timeout=request.timeout)
            mapped_status = _FETCH_STATUS[result.status]
            observation = result.observation

            child_urls: list[str] = []
            indicators: list[dict] = []
            title = None
            content_sha256 = None
            if observation is not None:
                title = observation.title
                content_sha256 = observation.content_sha256
                for item in observation.indicators:
                    indicators.append(
                        {"kind": item.kind.value, "value": item.value, "confidence": item.confidence}
                    )
                    if item.kind is DarkWebIndicatorKind.ONION_URL:
                        try:
                            child = self._canonicalize(item.value)
                        except ValueError:
                            continue
                        if child not in child_urls:
                            child_urls.append(child)
                        if len(child_urls) >= request.max_links_per_page:
                            break

            pages.append(
                OnionDiscoveryPage(
                    url=url,
                    depth=depth,
                    status=mapped_status,
                    title=title,
                    content_sha256=content_sha256,
                    discovered_onion_urls=tuple(child_urls),
                    indicator_count=len(indicators),
                    indicators=tuple(indicators),
                    error=result.error,
                    metadata={
                        **result.metadata,
                        "ahmia_blocklist_checked": blacklist_available,
                        "public_access_only": True,
                        "authentication_attempted": False,
                        "bypass_attempted": False,
                        "file_download_performed": False,
                        "raw_body_stored": False,
                        "page_text_stored": False,
                        "raw_secret_values_stored": False,
                    },
                )
            )
            if result.error:
                errors.append(f"{url}: {result.error}")

            if depth >= request.max_depth:
                continue
            for child in child_urls:
                if child not in queued:
                    queued.add(child)
                    discovered.append(child)
                    queue.append((child, depth + 1))

        any_success = any(page.status is OnionDiscoveryStatus.SUCCESS for page in pages)
        any_problem = bool(errors) or any(
            page.status in {
                OnionDiscoveryStatus.PARTIAL,
                OnionDiscoveryStatus.FAILED,
                OnionDiscoveryStatus.NOT_CONFIGURED,
            }
            for page in pages
        )
        if any_success and any_problem:
            overall = OnionDiscoveryStatus.PARTIAL
        elif any_success:
            overall = OnionDiscoveryStatus.SUCCESS
        elif pages and all(page.status is OnionDiscoveryStatus.BLOCKED for page in pages):
            overall = OnionDiscoveryStatus.BLOCKED
        elif pages:
            overall = OnionDiscoveryStatus.FAILED
        else:
            overall = OnionDiscoveryStatus.FAILED

        return OnionDiscoveryResult(
            request=request,
            status=overall,
            pages=pages,
            discovered_onion_urls=discovered,
            blocked_onion_urls=blocked,
            errors=errors,
            metadata={
                "ahmia_blocklist_checked": blacklist_available,
                "seed_count": len(seeds),
                "visited_count": len(visited),
                "page_count": len(pages),
                "discovered_onion_count": len(discovered),
                "blocked_count": len(blocked),
                "max_pages_reached": len(pages) >= request.max_pages and bool(queue),
                "raw_body_stored": False,
                "page_text_stored": False,
                "raw_secret_values_stored": False,
            },
        )

    @staticmethod
    def _canonicalize(url: str) -> str:
        valid = TorOnionHttpClient.validate_onion_url((url or "").strip())
        parsed = urlsplit(valid)
        host = (parsed.hostname or "").casefold().rstrip(".")
        netloc = host
        if parsed.port is not None:
            netloc += f":{parsed.port}"
        path = parsed.path or "/"
        # Discovery identity intentionally drops query/fragment to avoid tokens,
        # tracking values, and unbounded crawl fan-out.
        return urlunsplit((parsed.scheme.casefold(), netloc, path, "", ""))
