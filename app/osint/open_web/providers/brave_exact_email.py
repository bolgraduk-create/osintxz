# M021.16.5.2B — Brave broad exact-email public-web discovery.

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import settings
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebDocument,
    OpenWebProviderInfo,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.providers.live_web import LiveWebOpenWebProvider


class _BraveAuthError(RuntimeError):
    pass


class _BraveRateLimitError(RuntimeError):
    pass


class BraveExactEmailOpenWebProvider(OpenWebProvider):
    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        *,
        live_web_provider: LiveWebOpenWebProvider,
        transport=None,
        max_candidates: int = 40,
        max_pages: int = 2,
    ) -> None:
        self.live_web_provider = live_web_provider
        self.transport = transport
        self.max_candidates = max(1, min(int(max_candidates), 100))
        self.max_pages = max(1, min(int(max_pages), 5))
        self._info = OpenWebProviderInfo(
            name="brave_exact_email",
            display_name="Brave Exact Email",
            supported_targets=frozenset({OsintTargetType.EMAIL}),
            passive=True,
            public_data_only=True,
            requires_credentials=True,
            default_enabled=True,
            priority=10,
        )

    @property
    def info(self) -> OpenWebProviderInfo:
        return self._info

    def is_available(self) -> bool:
        key = settings.brave_search_api_key
        if key is None:
            return False
        return bool(key.get_secret_value().strip())

    def search(self, query: OpenWebQuery) -> OpenWebResult:
        if not self.supports(query):
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_SUPPORTED,
                error="EMAIL only.",
            )

        if not self.is_available():
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_AVAILABLE,
                error="BRAVE_SEARCH_API_KEY is not configured.",
                metadata={
                    "public_data_only": True,
                    "requires_credentials": True,
                },
            )

        email = query.value.strip()

        try:
            candidates, search_metadata = self._search_candidates(
                email=email,
                requested_limit=min(
                    self.max_candidates,
                    max(query.limit, 1),
                ),
                timeout=query.timeout,
            )
        except _BraveAuthError as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_AVAILABLE,
                error=str(exc),
                metadata={
                    "public_data_only": True,
                    "requires_credentials": True,
                    "authentication_failed": True,
                },
            )
        except _BraveRateLimitError as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.PARTIAL,
                error=str(exc),
                metadata={
                    "public_data_only": True,
                    "rate_limited": True,
                },
            )
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=str(exc) or exc.__class__.__name__,
                metadata={
                    "failure_isolated": True,
                    "public_data_only": True,
                    "candidate_source": "brave_web_search",
                },
            )

        verified_documents: list[OpenWebDocument] = []
        seen_urls: set[str] = set()
        checked = 0
        verification_failures = 0
        exact_misses = 0

        for candidate in candidates:
            candidate_url = self._candidate_url(candidate)
            if not candidate_url:
                continue

            key = candidate_url.casefold().rstrip("/")
            if key in seen_urls:
                continue

            seen_urls.add(key)
            checked += 1

            live_result = self.live_web_provider.search(
                OpenWebQuery(
                    target_type=OsintTargetType.URL,
                    value=candidate_url,
                    case_id=query.case_id,
                    limit=1,
                    timeout=query.timeout,
                    depth=query.depth,
                    parent_entity_id=query.parent_entity_id,
                )
            )

            if not live_result.usable:
                verification_failures += 1
                continue

            if not live_result.documents:
                continue

            live_document = live_result.documents[0]

            if not self._contains_exact_email(
                live_document.extraction_text,
                email,
            ):
                exact_misses += 1
                continue

            metadata = dict(live_document.metadata)
            metadata.update(
                {
                    "discovery_provider": self.info.name,
                    "candidate_source": "brave_web_search",
                    "exact_email_verified": True,
                    "exact_email": email.casefold(),
                    "brave_title": candidate.get("title"),
                    "brave_description": candidate.get("description"),
                    "brave_age": candidate.get("age"),
                    "brave_language": candidate.get("language"),
                    "public_data_only": True,
                }
            )

            verified_documents.append(
                OpenWebDocument(
                    url=live_document.url,
                    provider=self.info.name,
                    title=(
                        live_document.title
                        or self._clean_text(candidate.get("title"))
                    ),
                    snippet=None,
                    text=live_document.text,
                    captured_at=None,
                    content_type=live_document.content_type,
                    confidence=0.97,
                    reliability=0.92,
                    metadata=metadata,
                )
            )

            if len(verified_documents) >= query.limit:
                break

        status = OpenWebStatus.SUCCESS
        if (
            candidates
            and not verified_documents
            and verification_failures
        ):
            status = OpenWebStatus.PARTIAL

        return OpenWebResult(
            provider=self.info.name,
            status=status,
            documents=verified_documents,
            metadata={
                "query_strategy": (
                    "brave_exact_phrase_then_live_exact_verification"
                ),
                "candidate_source": "brave_web_search",
                "candidates_returned": len(candidates),
                "candidates_checked": checked,
                "verification_failures": verification_failures,
                "exact_misses": exact_misses,
                "verified_documents": len(verified_documents),
                "exact_match_required": True,
                "public_data_only": True,
                "corpus_scope": "broad_web",
                **search_metadata,
            },
        )

    def _search_candidates(
        self,
        *,
        email: str,
        requested_limit: int,
        timeout: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        token = (
            settings.brave_search_api_key
            .get_secret_value()
            .strip()
        )

        candidates: list[dict[str, Any]] = []
        seen: set[str] = set()
        pages_requested = 0
        more_results_available = True
        page_size = min(20, max(1, requested_limit))

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            verify=self.live_web_provider._tls_context(),
            transport=self.transport,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": token,
                "User-Agent": (
                    "OSINTXZ/1.0 BraveExactEmailOpenWebProvider"
                ),
            },
        ) as client:
            for offset in range(self.max_pages):
                if (
                    len(candidates) >= requested_limit
                    or not more_results_available
                ):
                    break

                response = client.get(
                    self.API_URL,
                    params={
                        "q": f'"{email}"',
                        "count": page_size,
                        "offset": offset,
                        "safesearch": "moderate",
                    },
                )
                pages_requested += 1

                if response.status_code in {401, 403}:
                    raise _BraveAuthError(
                        "Brave Search API rejected the API key."
                    )

                if response.status_code == 429:
                    raise _BraveRateLimitError(
                        "Brave Search API rate limit reached."
                    )

                response.raise_for_status()

                try:
                    payload = response.json()
                except Exception as exc:
                    raise ValueError(
                        "Brave Search API returned invalid JSON."
                    ) from exc

                if not isinstance(payload, dict):
                    break

                web = payload.get("web")
                results = (
                    web.get("results", [])
                    if isinstance(web, dict)
                    else []
                )

                if not isinstance(results, list):
                    results = []

                for item in results:
                    if not isinstance(item, dict):
                        continue

                    url = self._candidate_url(item)
                    if not url:
                        continue

                    key = url.casefold().rstrip("/")
                    if key in seen:
                        continue

                    seen.add(key)
                    candidates.append(item)

                    if len(candidates) >= requested_limit:
                        break

                query_meta = payload.get("query")
                more_results_available = bool(
                    query_meta.get(
                        "more_results_available",
                        False,
                    )
                    if isinstance(query_meta, dict)
                    else False
                )

        return (
            candidates[:requested_limit],
            {
                "search_pages_requested": pages_requested,
                "search_page_size": page_size,
                "more_results_available": more_results_available,
            },
        )

    @classmethod
    def _contains_exact_email(
        cls,
        text: str,
        email: str,
    ) -> bool:
        normalized = email.strip().casefold()
        if not normalized:
            return False

        pattern = re.compile(
            r"(?<![A-Z0-9._%+\-])"
            + re.escape(normalized)
            + r"(?![A-Z0-9._%+\-])",
            re.IGNORECASE,
        )
        return bool(pattern.search(text))

    @staticmethod
    def _candidate_url(candidate: dict[str, Any]) -> str | None:
        value = candidate.get("url")
        if not isinstance(value, str):
            return None

        value = value.strip()
        if not value.startswith(("https://", "http://")):
            return None
        return value

    @staticmethod
    def _clean_text(value: object) -> str | None:
        if not isinstance(value, str):
            return None

        value = value.strip()
        return value or None
