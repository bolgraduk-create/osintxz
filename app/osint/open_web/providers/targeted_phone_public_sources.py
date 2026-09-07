from __future__ import annotations

from dataclasses import dataclass
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
from app.osint.open_web.public_document_fetcher import (
    PublicDocumentTextFetcher,
)
from app.osint.phone_intelligence import PhoneIntelligenceService


@dataclass(frozen=True, slots=True)
class PhonePublicSourceRule:
    name: str
    domains: tuple[str, ...]
    tier: str
    confidence: float
    reliability: float
    notes: str


class TargetedPhonePublicSourcesProvider(OpenWebProvider):
    _PHONEISH = re.compile(r"(?<!\d)\+?\d[\d\s().\-]{5,}\d(?!\d)")

    DEFAULT_RULES: tuple[PhonePublicSourceRule, ...] = (
        PhonePublicSourceRule(
            name="prozorro",
            domains=("prozorro.gov.ua",),
            tier="A_OFFICIAL_PUBLIC",
            confidence=0.96,
            reliability=0.97,
            notes="Official Ukrainian public procurement domain.",
        ),
        PhonePublicSourceRule(
            name="dzo",
            domains=("dzo.com.ua",),
            tier="A_PUBLIC_PROCUREMENT",
            confidence=0.94,
            reliability=0.94,
            notes="Public procurement marketplace / tender pages.",
        ),
        PhonePublicSourceRule(
            name="youcontrol",
            domains=("youcontrol.com.ua",),
            tier="B_PUBLIC_BUSINESS_DIRECTORY",
            confidence=0.91,
            reliability=0.90,
            notes="Public company/sole-trader directory pages; contact data may be historical.",
        ),
    )

    def __init__(
        self,
        *,
        base_url: str | None = None,
        transport=None,
        live_web: LiveWebOpenWebProvider | None = None,
        rules: tuple[PhonePublicSourceRule, ...] | None = None,
        user_agent: str = "OSINTXZ/1.0 TargetedPhonePublicSources",
        max_candidates: int = 60,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("SEARXNG_BASE_URL")
            or "http://127.0.0.1:8081"
        ).rstrip("/")
        self.transport = transport
        self.live_web = live_web or LiveWebOpenWebProvider()
        self.document_fetcher = PublicDocumentTextFetcher(
            live_web=self.live_web,
            transport=transport,
        )
        self.rules = rules or self.DEFAULT_RULES
        self.user_agent = user_agent
        self.max_candidates = max(1, min(int(max_candidates), 120))
        self.phone_service = PhoneIntelligenceService()
        self._info = OpenWebProviderInfo(
            name="targeted_phone_public_sources",
            display_name="Targeted Phone Public Sources",
            supported_targets=frozenset({OsintTargetType.PHONE}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=8,
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
            self._validate_base_url()
            plans = self._build_query_plans(intelligence)
            candidates = self._discover_candidates(
                plans,
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
                    "public_data_only": True,
                    "credentials_required": False,
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

            rule = self._rule_for_url(url)
            if rule is None:
                rejected += 1
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

            document = None

            if live_result.usable and live_result.documents:
                document = live_result.documents[0]
            else:
                outcome = self.document_fetcher.fetch(
                    url,
                    timeout=query.timeout,
                )
                document = outcome.document

            if document is None:
                fetch_failures += 1
                continue
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
                    "candidate_engine": candidate.get("engine"),
                    "candidate_query": candidate.get("_phone_query"),
                    "source_rule": rule.name,
                    "source_tier": rule.tier,
                    "source_rule_notes": rule.notes,
                    "exact_phone_verified": True,
                    "matched_phone_digits": matched,
                    "public_data_only": True,
                    "source_targeted": True,
                    "document_aware_verification": True,
                    "content_extraction_kind": (
                        document.metadata.get("extraction_kind")
                        or "live_web_text"
                    ),
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
                    confidence=rule.confidence,
                    reliability=rule.reliability,
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
                "query_strategy": "source_targeted_phone_then_exact_live_verify",
                "source_rules": [
                    {
                        "name": rule.name,
                        "domains": list(rule.domains),
                        "tier": rule.tier,
                    }
                    for rule in self.rules
                ],
                "query_count": len(plans),
                "candidate_count": len(candidates),
                "verified_count": len(documents),
                "rejected_count": rejected,
                "candidate_fetch_failures": fetch_failures,
                "public_data_only": True,
                "credentials_required": False,
            },
        )

    def _build_query_plans(self, intelligence) -> tuple[dict[str, str], ...]:
        phone_variants = self._phone_search_values(intelligence)
        plans: list[dict[str, str]] = []

        for rule in self.rules:
            for domain in rule.domains:
                for value in phone_variants:
                    plans.append(
                        {
                            "query": f"{value} site:{domain}",
                            "rule": rule.name,
                            "domain": domain,
                        }
                    )

        return tuple(plans[:24])

    @staticmethod
    def _phone_search_values(intelligence) -> tuple[str, ...]:
        values: list[str] = []

        def add(value: str | None) -> None:
            if not value:
                return
            text = " ".join(str(value).strip().split())
            if text and text not in values:
                values.append(text)

        if intelligence.e164:
            add(re.sub(r"\D+", "", intelligence.e164))
        if intelligence.national:
            add(re.sub(r"\D+", "", intelligence.national))

        add(intelligence.e164)
        add(intelligence.national)

        return tuple(values[:4])

    def _discover_candidates(
        self,
        plans: tuple[dict[str, str], ...],
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
            for plan in plans:
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

                    rule = self._rule_for_url(url)
                    if rule is None:
                        continue

                    key = url.casefold()
                    if key in seen:
                        continue

                    seen.add(key)
                    enriched = dict(item)
                    enriched["_phone_query"] = plan["query"]
                    enriched["_source_rule"] = rule.name
                    results.append(enriched)

                    if len(results) >= limit:
                        break

        return results

    def _rule_for_url(self, url: str) -> PhonePublicSourceRule | None:
        try:
            host = (urlsplit(url).hostname or "").casefold()
        except Exception:
            return None

        for rule in self.rules:
            for domain in rule.domains:
                allowed = domain.casefold()
                if host == allowed or host.endswith("." + allowed):
                    return rule

        return None

    def _validate_base_url(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("SEARXNG_BASE_URL must use http or https.")

        host = (parsed.hostname or "").casefold()
        allow_remote = (
            os.getenv("SEARXNG_ALLOW_REMOTE", "").strip().casefold()
            in {"1", "true", "yes"}
        )

        if host not in {"127.0.0.1", "localhost", "::1"} and not allow_remote:
            raise ValueError("Remote SearXNG endpoints are disabled by default.")

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
