"""
M021.16.5.2A — GDELT exact-email public-web discovery.

GDELT discovers candidate public article URLs.
Each candidate is fetched through the existing LiveWebOpenWebProvider and
accepted only when the exact queried email is present in visible page text.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

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


class GdeltExactEmailOpenWebProvider(OpenWebProvider):
    API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(
        self,
        *,
        live_web_provider: LiveWebOpenWebProvider,
        transport=None,
        max_candidates: int = 15,
    ) -> None:
        self.live_web_provider = live_web_provider
        self.transport = transport
        self.max_candidates = max(1, min(int(max_candidates), 25))
        self._info = OpenWebProviderInfo(
            name="gdelt_exact_email",
            display_name="GDELT Exact Email",
            supported_targets=frozenset({OsintTargetType.EMAIL}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=20,
        )

    @property
    def info(self) -> OpenWebProviderInfo:
        return self._info

    def search(self, query: OpenWebQuery) -> OpenWebResult:
        if not self.supports(query):
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_SUPPORTED,
                error="EMAIL only.",
            )

        email = query.value.strip()
        candidate_limit = min(query.limit, self.max_candidates)

        try:
            articles = self._search_candidates(
                email=email,
                limit=candidate_limit,
                timeout=query.timeout,
            )
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=str(exc) or exc.__class__.__name__,
                metadata={
                    "failure_isolated": True,
                    "public_data_only": True,
                    "candidate_source": "gdelt_doc_2",
                },
            )

        verified_documents: list[OpenWebDocument] = []
        verification_failures = 0
        checked = 0
        seen_urls: set[str] = set()

        for article in articles:
            candidate_url = self._article_url(article)
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
                continue

            metadata = dict(live_document.metadata)
            metadata.update(
                {
                    "discovery_provider": self.info.name,
                    "candidate_source": "gdelt_doc_2",
                    "exact_email_verified": True,
                    "exact_email": email.casefold(),
                    "gdelt_title": article.get("title"),
                    "gdelt_domain": article.get("domain"),
                    "gdelt_language": article.get("language"),
                    "gdelt_source_country": article.get("sourcecountry"),
                    "gdelt_seen_date": article.get("seendate"),
                    "public_data_only": True,
                }
            )

            verified_documents.append(
                OpenWebDocument(
                    url=live_document.url,
                    provider=self.info.name,
                    title=(
                        live_document.title
                        or self._clean_text(article.get("title"))
                    ),
                    snippet=None,
                    text=live_document.text,
                    captured_at=self._clean_text(article.get("seendate")),
                    content_type=live_document.content_type,
                    confidence=0.95,
                    reliability=0.90,
                    metadata=metadata,
                )
            )

            if len(verified_documents) >= query.limit:
                break

        status = OpenWebStatus.SUCCESS

        if articles and not verified_documents and verification_failures:
            status = OpenWebStatus.PARTIAL

        return OpenWebResult(
            provider=self.info.name,
            status=status,
            documents=verified_documents,
            metadata={
                "query_strategy": (
                    "gdelt_exact_phrase_then_live_exact_verification"
                ),
                "candidate_source": "gdelt_doc_2",
                "candidates_returned": len(articles),
                "candidates_checked": checked,
                "verification_failures": verification_failures,
                "verified_documents": len(verified_documents),
                "exact_match_required": True,
                "public_data_only": True,
                "corpus_scope": "news_media",
            },
        )

    def _search_candidates(
        self,
        *,
        email: str,
        limit: int,
        timeout: int,
    ) -> list[dict[str, Any]]:
        params = {
            "query": f'"{email}"',
            "mode": "artlist",
            "format": "json",
            "maxrecords": limit,
            "sort": "datedesc",
            "timespan": "3months",
        }

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            verify=self.live_web_provider._tls_context(),
            transport=self.transport,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "OSINTXZ/1.0 GdeltExactEmailOpenWebProvider"
                ),
            },
        ) as client:
            response = client.get(self.API_URL, params=params)
            response.raise_for_status()

        try:
            payload = response.json()
        except Exception as exc:
            raise ValueError("GDELT returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            return []

        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            return []

        return [
            item
            for item in articles
            if isinstance(item, dict)
        ][:limit]

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
    def _article_url(article: dict[str, Any]) -> str | None:
        value = article.get("url")
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
