from __future__ import annotations

import hashlib
from urllib.parse import urljoin

import httpx

from app.darkweb_intelligence.contracts import (
    DarkWebFetchResult,
    DarkWebFetchStatus,
    DarkWebPageObservation,
)
from app.darkweb_intelligence.extractor import DarkWebIndicatorExtractor
from app.darkweb_intelligence.tor_client import TorOnionHttpClient
from app.intelligence_sources.policy import IntelligenceDataSanitizer


class DarkWebIntelligenceService:
    def __init__(
        self,
        *,
        client: TorOnionHttpClient,
        extractor: DarkWebIndicatorExtractor | None = None,
        data_sanitizer: IntelligenceDataSanitizer | None = None,
    ) -> None:
        self.client = client
        self.extractor = extractor or DarkWebIndicatorExtractor()
        self.data_sanitizer = data_sanitizer or IntelligenceDataSanitizer()

    def fetch_public_onion(
        self,
        url: str,
        *,
        timeout: int = 30,
    ) -> DarkWebFetchResult:
        try:
            page = self.client.fetch(url, timeout=timeout)
        except ImportError as exc:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.NOT_CONFIGURED,
                error=str(exc),
                metadata={"tor_socks_dependency_missing": True},
            )
        except ValueError as exc:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.BLOCKED,
                error=str(exc),
                metadata={"policy_block": True},
            )
        except httpx.ProxyError as exc:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.NOT_CONFIGURED,
                error=str(exc),
                metadata={"tor_proxy_unavailable": True},
            )
        except httpx.RequestError as exc:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        except Exception as exc:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

        code = page.status_code
        if code in {401, 403, 407}:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.BLOCKED,
                error=f"Onion resource requires or rejected access (HTTP {code}); no bypass attempted.",
                metadata={
                    "authentication_attempted": False,
                    "bypass_attempted": False,
                },
            )

        if 300 <= code < 400:
            redirect_to = None
            if page.location:
                try:
                    candidate = urljoin(page.url, page.location)
                    redirect_to = TorOnionHttpClient.validate_onion_url(candidate)
                except ValueError:
                    redirect_to = None
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.PARTIAL,
                error="Redirect not followed automatically.",
                metadata={
                    "status_code": code,
                    "redirect_to": redirect_to,
                    "redirects_followed": False,
                },
            )

        if code == 429 or code >= 500:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.PARTIAL,
                error=f"Onion HTTP {code}.",
                metadata={
                    "retryable": True,
                    "rate_limited": code == 429,
                },
            )

        if code >= 400:
            return DarkWebFetchResult(
                status=DarkWebFetchStatus.FAILED,
                error=f"Onion HTTP {code}.",
                metadata={"retryable": False},
            )

        title, indicators = self.extractor.extract(
            source_url=page.url,
            body=page.body,
            content_type=page.content_type,
        )

        observation = DarkWebPageObservation(
            source_url=page.url,
            status_code=code,
            title=title,
            content_sha256=hashlib.sha256(page.body).hexdigest(),
            indicators=indicators,
            metadata={
                "content_type": page.content_type,
                "content_length": len(page.body),
                "public_access_only": True,
                "authentication_attempted": False,
                "bypass_attempted": False,
                "redirects_followed": False,
                "file_download_performed": False,
                "raw_body_stored": False,
                "page_text_stored": False,
                "secret_material_stored": False,
            },
        )
        sanitized = self.data_sanitizer.sanitize(observation)

        return DarkWebFetchResult(
            status=DarkWebFetchStatus.SUCCESS,
            observation=sanitized.value,
            metadata={
                "indicator_count": len(indicators),
                "secret_fields_redacted": sanitized.redacted_count,
                "raw_body_stored": False,
            },
        )
