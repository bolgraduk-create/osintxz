from __future__ import annotations

import re
import ssl
from typing import Any

import httpx

try:
    import truststore
except ImportError:  # pragma: no cover - optional dependency
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
from app.osint.open_web.providers.live_web import LiveWebOpenWebProvider
from app.osint.phone_intelligence import PhoneIntelligenceService


class GdeltPhoneExactOpenWebProvider(OpenWebProvider):
    """
    Free/public exact-phone discovery over the GDELT DOC 2.0 news corpus.

    GDELT is used only to discover candidate public article URLs. Every
    candidate is then fetched through the existing bounded Live Web provider
    and accepted only when the requested phone number is present in visible
    page text. Search-engine hits alone are never promoted as evidence.
    """

    API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    _PHONEISH = re.compile(r"(?<!\d)\+?\d[\d\s().\-]{5,}\d(?!\d)")

    def __init__(
        self,
        *,
        transport=None,
        live_web: LiveWebOpenWebProvider | None = None,
        user_agent: str = "OSINTXZ/1.0 GDELTPhoneExact",
        max_candidates: int = 25,
    ) -> None:
        self.transport = transport
        self.live_web = live_web or LiveWebOpenWebProvider()
        self.user_agent = user_agent
        self.max_candidates = max(1, min(int(max_candidates), 75))
        self.phone_service = PhoneIntelligenceService()
        self._info = OpenWebProviderInfo(
            name="gdelt_phone_exact",
            display_name="GDELT Exact Phone",
            supported_targets=frozenset({OsintTargetType.PHONE}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=15,
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
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=f"Phone normalization failed: {exc}",
                metadata={
                    "failure_isolated": True,
                    "public_data_only": True,
                },
            )

        exact_values = self._exact_values(intelligence)
        if not exact_values:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.SUCCESS,
                documents=[],
                metadata={
                    "query_strategy": "exact_phone_phrase_then_live_verify",
                    "candidate_count": 0,
                    "verified_count": 0,
                    "public_data_only": True,
                    "news_corpus_only": True,
                },
            )

        gdelt_query = self._build_gdelt_query(exact_values)

        try:
            candidates = self._search_candidates(
                gdelt_query,
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
                    "query_strategy": "exact_phone_phrase_then_live_verify",
                    "public_data_only": True,
                    "news_corpus_only": True,
                },
            )

        documents: list[OpenWebDocument] = []
        seen_urls: set[str] = set()
        rejected = 0
        fetch_failures = 0

        target_digit_sets = self._target_digit_sets(intelligence)

        for candidate in candidates:
            url = str(candidate.get("url") or "").strip()
            if not url:
                continue
            key = url.casefold()
            if key in seen_urls:
                continue
            seen_urls.add(key)

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
            matched_digits = self._matching_phone_digits(
                document.extraction_text,
                target_digit_sets,
            )
            if matched_digits is None:
                rejected += 1
                continue

            metadata = dict(document.metadata)
            metadata.update(
                {
                    "candidate_provider": "GDELT DOC 2.0",
                    "exact_phone_verified": True,
                    "matched_phone_digits": matched_digits,
                    "gdelt_title": candidate.get("title"),
                    "gdelt_domain": candidate.get("domain"),
                    "gdelt_language": candidate.get("language"),
                    "gdelt_source_country": candidate.get("sourcecountry"),
                    "gdelt_seen_date": candidate.get("seendate"),
                    "query_strategy": "exact_phone_phrase_then_live_verify",
                    "public_data_only": True,
                    "news_corpus_only": True,
                }
            )

            documents.append(
                OpenWebDocument(
                    url=document.url,
                    provider=self.info.name,
                    title=document.title or candidate.get("title"),
                    snippet=document.snippet,
                    text=document.text,
                    captured_at=document.captured_at or candidate.get("seendate"),
                    content_type=document.content_type,
                    confidence=0.90,
                    reliability=0.88,
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
                "query_strategy": "exact_phone_phrase_then_live_verify",
                "query_phrases": list(exact_values),
                "candidate_count": len(candidates),
                "verified_count": len(documents),
                "rejected_without_exact_phone": rejected,
                "candidate_fetch_failures": fetch_failures,
                "public_data_only": True,
                "news_corpus_only": True,
                "credentials_required": False,
            },
        )

    def _search_candidates(
        self,
        query_text: str,
        *,
        limit: int,
        timeout: int,
    ) -> list[dict[str, Any]]:
        params = {
            "query": query_text,
            "mode": "artlist",
            "maxrecords": max(1, min(int(limit), 75)),
            "format": "json",
            "sort": "hybridrel",
        }

        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            verify=self._tls_context(),
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        ) as client:
            response = client.get(self.API_URL, params=params)
            response.raise_for_status()
            payload = response.json()

        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        return [item for item in articles if isinstance(item, dict)]

    @staticmethod
    def _build_gdelt_query(values: tuple[str, ...]) -> str:
        quoted = [f'"{value}"' for value in values if value]
        if not quoted:
            return ""
        if len(quoted) == 1:
            return quoted[0]
        return "(" + " OR ".join(quoted) + ")"

    @staticmethod
    def _exact_values(intelligence) -> tuple[str, ...]:
        values: list[str] = []
        for value in (
            intelligence.e164,
            intelligence.international,
            intelligence.national,
        ):
            text = str(value or "").strip()
            if text and text not in values:
                values.append(text)
        return tuple(values[:4])

    @staticmethod
    def _target_digit_sets(intelligence) -> frozenset[str]:
        values: set[str] = set()
        for value in (
            intelligence.e164,
            intelligence.international,
            intelligence.national,
        ):
            digits = re.sub(r"\D+", "", str(value or ""))
            if len(digits) >= 7:
                values.add(digits)
        return frozenset(values)

    @classmethod
    def _matching_phone_digits(
        cls,
        text: str,
        target_digit_sets: frozenset[str],
    ) -> str | None:
        if not text or not target_digit_sets:
            return None

        for match in cls._PHONEISH.finditer(text):
            digits = re.sub(r"\D+", "", match.group(0))
            if digits in target_digit_sets:
                return digits
        return None

    @staticmethod
    def _tls_context():
        if truststore is not None:
            try:
                return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            except Exception:
                pass
        return ssl.create_default_context()
