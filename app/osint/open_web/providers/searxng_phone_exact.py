from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit

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
from app.osint.phone_intelligence import PhoneIntelligenceService


class SearxngPhoneExactOpenWebProvider(OpenWebProvider):
    """
    Broad PHONE candidate discovery through a user-controlled SearXNG instance.

    Candidate search is recall-oriented; Evidence admission is not.
    Every candidate URL must be fetched through the existing bounded LiveWeb
    provider and must contain the target phone digits in visible text.

    No login, CAPTCHA bypass, proxy rotation, browser anti-detection, or
    access-control circumvention is performed here.
    """

    _PHONEISH = re.compile(r"(?<!\d)\+?\d[\d\s().\-]{5,}\d(?!\d)")

    def __init__(
        self,
        *,
        base_url: str | None = None,
        transport=None,
        live_web: LiveWebOpenWebProvider | None = None,
        user_agent: str = "OSINTXZ/1.0 SearXNGPhoneExact",
        max_candidates: int = 40,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("SEARXNG_BASE_URL")
            or "http://127.0.0.1:8081"
        ).rstrip("/")
        self.transport = transport
        self.live_web = live_web or LiveWebOpenWebProvider()
        self.user_agent = user_agent
        self.max_candidates = max(1, min(int(max_candidates), 100))
        self.phone_service = PhoneIntelligenceService()

        self._info = OpenWebProviderInfo(
            name="searxng_phone_exact",
            display_name="SearXNG Exact Phone",
            supported_targets=frozenset({OsintTargetType.PHONE}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=12,
        )

    @property
    def info(self) -> OpenWebProviderInfo:
        return self._info

    def search(self, query: OpenWebQuery) -> OpenWebResult:
        if not self.supports(query):
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_SUPPORTED,
                error="PHONE only.",
            )

        try:
            intelligence = self.phone_service.analyze(query.value)
            query_plans = self._query_plans(intelligence)
            self._validate_base_url()
            candidates = self._discover_candidates(
                query_plans,
                limit=min(query.limit, self.max_candidates),
                timeout=query.timeout,
            )
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=str(exc) or exc.__class__.__name__,
                metadata={
                    "failure_isolated": True,
                    "query_strategy": (
                        "searxng_broad_phone_then_exact_live_verify"
                    ),
                    "searxng_base_url": self.base_url,
                    "public_data_only": True,
                },
            )

        target_digit_sets = self._target_digit_sets(intelligence)
        documents: list[OpenWebDocument] = []
        rejected = 0
        fetch_failures = 0

        for candidate in candidates:
            url = str(candidate.get("url") or "").strip()
            if not url:
                continue

            live_result = self.live_web.search(
                OpenWebQuery(
                    target_type=OsintTargetType.URL,
                    value=url,
                    case_id=query.case_id,
                    limit=1,
                    timeout=query.timeout,
                    depth=query.depth,
                    parent_entity_id=query.parent_entity_id,
                )
            )

            if not live_result.usable or not live_result.documents:
                fetch_failures += 1
                continue

            document = live_result.documents[0]
            matched = self._matching_phone_digits(
                document.extraction_text,
                target_digit_sets,
            )

            if matched is None:
                rejected += 1
                continue

            metadata = dict(document.metadata)
            metadata.update(
                {
                    "candidate_provider": "SearXNG",
                    "candidate_title": candidate.get("title"),
                    "candidate_snippet": candidate.get("content"),
                    "candidate_engine": candidate.get("engine"),
                    "candidate_query": candidate.get("_phone_query"),
                    "candidate_query_kind": candidate.get(
                        "_phone_query_kind"
                    ),
                    "exact_phone_verified": True,
                    "matched_phone_digits": matched,
                    "query_strategy": (
                        "searxng_broad_phone_then_exact_live_verify"
                    ),
                    "public_data_only": True,
                }
            )

            documents.append(
                OpenWebDocument(
                    url=document.url,
                    provider=self.info.name,
                    title=document.title or candidate.get("title"),
                    snippet=document.snippet or candidate.get("content"),
                    text=document.text,
                    captured_at=document.captured_at,
                    content_type=document.content_type,
                    confidence=0.92,
                    reliability=0.90,
                    metadata=metadata,
                )
            )

            if len(documents) >= query.limit:
                break

        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.SUCCESS,
            documents=documents,
            metadata={
                "query_strategy": (
                    "searxng_broad_phone_then_exact_live_verify"
                ),
                "candidate_queries": [
                    plan["query"]
                    for plan in query_plans
                ],
                "candidate_count": len(candidates),
                "verified_count": len(documents),
                "rejected_without_exact_phone": rejected,
                "candidate_fetch_failures": fetch_failures,
                "searxng_base_url": self.base_url,
                "public_data_only": True,
                "credentials_required": False,
            },
        )

    def _discover_candidates(
        self,
        query_plans: tuple[dict[str, str], ...],
        *,
        limit: int,
        timeout: int,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        results: list[dict[str, Any]] = []

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        ) as client:
            for plan in query_plans:
                if len(results) >= limit:
                    break

                response = client.get(
                    f"{self.base_url}/search",
                    params={
                        "q": plan["query"],
                        "format": "json",
                        "categories": "general",
                        "safesearch": 0,
                    },
                )
                response.raise_for_status()
                payload = response.json()

                raw_results = (
                    payload.get("results", [])
                    if isinstance(payload, dict)
                    else []
                )

                for item in raw_results:
                    if not isinstance(item, dict):
                        continue

                    url = str(item.get("url") or "").strip()
                    if not url:
                        continue

                    key = url.casefold()
                    if key in seen:
                        continue

                    seen.add(key)

                    enriched = dict(item)
                    enriched["_phone_query"] = plan["query"]
                    enriched["_phone_query_kind"] = plan["kind"]
                    results.append(enriched)

                    if len(results) >= limit:
                        break

        return results

    def _validate_base_url(self) -> None:
        parsed = urlsplit(self.base_url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "SEARXNG_BASE_URL must use http or https."
            )

        host = (parsed.hostname or "").casefold()
        allow_remote = (
            os.getenv("SEARXNG_ALLOW_REMOTE", "")
            .strip()
            .casefold()
            in {"1", "true", "yes"}
        )

        if (
            host not in {"127.0.0.1", "localhost", "::1"}
            and not allow_remote
        ):
            raise ValueError(
                "Remote SearXNG endpoints are disabled by default. "
                "Use a local instance or explicitly set "
                "SEARXNG_ALLOW_REMOTE=1."
            )

    @staticmethod
    def _query_plans(
        intelligence,
    ) -> tuple[dict[str, str], ...]:
        """
        Bounded recall-oriented phone queries.

        Search results are candidate locators only. Broad variants are safe
        here because exact visible-text verification remains mandatory.
        """
        plans: list[dict[str, str]] = []
        seen: set[str] = set()

        def add(kind: str, value: str | None) -> None:
            if not value:
                return
            query = " ".join(str(value).strip().split())
            if not query or query in seen:
                return
            seen.add(query)
            plans.append(
                {
                    "kind": kind,
                    "query": query,
                }
            )

        e164 = intelligence.e164
        international = intelligence.international
        national = intelligence.national

        e164_digits = (
            re.sub(r"\D+", "", e164)
            if e164
            else ""
        )
        national_digits = (
            re.sub(r"\D+", "", national)
            if national
            else ""
        )

        add("e164_digits_broad", e164_digits)
        add("national_digits_broad", national_digits)
        add("e164_broad", e164)
        add("national_formatted_broad", national)
        add("international_formatted_broad", international)

        if e164_digits:
            add(
                "e164_digits_exact",
                f'"{e164_digits}"',
            )

        return tuple(plans[:6])

    @staticmethod
    def _target_digit_sets(intelligence) -> set[str]:
        values: set[str] = set()

        for value in (
            intelligence.e164,
            intelligence.international,
            intelligence.national,
        ):
            digits = re.sub(r"\D+", "", str(value or ""))
            if digits:
                values.add(digits)

        return values

    @classmethod
    def _matching_phone_digits(
        cls,
        text: str,
        target_digit_sets: set[str],
    ) -> str | None:
        if not text or not target_digit_sets:
            return None

        for match in cls._PHONEISH.finditer(text):
            digits = re.sub(r"\D+", "", match.group(0))
            if digits in target_digit_sets:
                return digits

        return None
