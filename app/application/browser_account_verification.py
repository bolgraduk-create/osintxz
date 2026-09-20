"""R13.26a.3 — browser-assisted verification for ambiguous username accounts.

The HTTP validator stays the cheap first pass.  This module is only invoked for
ambiguous account URLs (reported/unreachable) and uses Crawlee + Playwright to
observe the rendered page after JavaScript execution.

Important safety/quality rules:
- browser verification is optional and must never break a search if unavailable;
- absence of positive evidence is not treated as proof that an account is absent;
- INVALID requires direct negative evidence (404/410, rendered not-found marker,
  or a clear redirect away from the username to a generic page);
- browser results are ephemeral diagnostics; no screenshots/body dumps are
  persisted;
- Crawlee uses MemoryStorageClient so verification does not create crawl files.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
import importlib.util
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit

from app.application.identity_resolution import is_account_candidate_type
from app.application.account_profile_validation import (
    _bounded_username_occurrence,
    _looks_like_auth_wall,
    _not_found_marker,
    _profile_vocabulary_signal,
    _public_url,
    _safe_public_url,
    _username_for_row,
    _username_url_relation,
)


_BROWSER_REVIEW_STATUSES = {"reported", "unreachable"}
_BROWSER_FINAL_STATUSES = {
    "verified",
    "likely",
    "uncertain",
    "blocked",
    "invalid",
    "unavailable",
}
_BLOCK_MARKERS = (
    "verify you are human",
    "checking your browser",
    "attention required",
    "access denied",
    "captcha",
    "cloudflare",
    "enable javascript and cookies",
    "temporarily blocked",
    "too many requests",
)


@dataclass(frozen=True, slots=True)
class BrowserProfileCandidate:
    url: str
    username: str
    source: str = ""
    service: str = ""
    provider_corroboration: int = 1


@dataclass(frozen=True, slots=True)
class BrowserVerificationResult:
    status: str
    reason: str
    checked: bool
    final_url: str = ""
    http_status: int | None = None
    title: str = ""
    username_seen: bool = False
    evidence_score: float = 0.0
    evidence_signals: tuple[str, ...] = ()
    negative_signal: str = ""
    backend: str = "crawlee_playwright"

    def row_fields(self) -> dict[str, Any]:
        return {
            "accountBrowserVerificationStatus": self.status,
            "accountBrowserVerificationReason": self.reason,
            "accountBrowserVerificationChecked": self.checked,
            "accountBrowserVerificationFinalUrl": self.final_url,
            "accountBrowserVerificationHttpStatus": self.http_status,
            "accountBrowserVerificationTitle": self.title,
            "accountBrowserVerificationUsernameSeen": self.username_seen,
            "accountBrowserVerificationEvidenceScore": round(
                float(self.evidence_score), 1
            ),
            "accountBrowserVerificationEvidenceSignals": list(
                self.evidence_signals
            ),
            "accountBrowserVerificationNegativeSignal": self.negative_signal,
            "accountBrowserVerificationBackend": self.backend,
        }


@dataclass(frozen=True, slots=True)
class BrowserVerificationSummary:
    available: bool
    checked: int
    verified: int
    likely: int
    uncertain: int
    blocked: int
    invalid: int
    unavailable: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "checked": self.checked,
            "verified": self.verified,
            "likely": self.likely,
            "uncertain": self.uncertain,
            "blocked": self.blocked,
            "invalid": self.invalid,
            "unavailable": self.unavailable,
            "error": self.error,
        }


class BrowserAccountVerifier:
    """Bounded Crawlee/Playwright verifier for rendered public profile pages."""

    BACKEND = "crawlee_playwright"

    @staticmethod
    def dependency_available() -> bool:
        return bool(
            importlib.util.find_spec("crawlee")
            and importlib.util.find_spec("playwright")
        )

    def verify(
        self,
        candidates: Iterable[BrowserProfileCandidate],
        *,
        max_checks: int = 14,
        navigation_timeout: float = 10.0,
        max_concurrency: int = 3,
    ) -> tuple[dict[str, BrowserVerificationResult], BrowserVerificationSummary]:
        unique: dict[str, BrowserProfileCandidate] = {}
        for candidate in candidates:
            safe_url, _reason = _safe_public_url(candidate.url)
            if not safe_url:
                continue
            key = _canonical_url(safe_url)
            unique.setdefault(key, candidate)

        ordered = sorted(
            unique.values(),
            key=lambda item: (
                -int(item.provider_corroboration or 1),
                0 if str(item.source or "").casefold() == "sherlock" else 1,
                item.url.casefold(),
            ),
        )[: max(0, int(max_checks))]

        if not ordered:
            return {}, BrowserVerificationSummary(
                available=self.dependency_available(),
                checked=0,
                verified=0,
                likely=0,
                uncertain=0,
                blocked=0,
                invalid=0,
                unavailable=0,
            )

        if not self.dependency_available():
            results = {
                _canonical_url(item.url): BrowserVerificationResult(
                    status="unavailable",
                    reason=(
                        "Browser verification is not installed. Install the "
                        "account-verification extra and Chromium."
                    ),
                    checked=False,
                    final_url=item.url,
                )
                for item in ordered
            }
            return results, _summarize(
                results,
                available=False,
                error="Crawlee/Playwright is not installed.",
            )

        try:
            results = _run_async(
                self._verify_async(
                    ordered,
                    navigation_timeout=navigation_timeout,
                    max_concurrency=max_concurrency,
                )
            )
            return results, _summarize(results, available=True)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            results = {
                _canonical_url(item.url): BrowserVerificationResult(
                    status="unavailable",
                    reason=f"Browser verification backend could not start: {reason}",
                    checked=False,
                    final_url=item.url,
                )
                for item in ordered
            }
            return results, _summarize(
                results,
                available=False,
                error=reason,
            )

    async def _verify_async(
        self,
        candidates: list[BrowserProfileCandidate],
        *,
        navigation_timeout: float,
        max_concurrency: int,
    ) -> dict[str, BrowserVerificationResult]:
        # Imported lazily so the normal application has no hard browser
        # dependency and can run without Chromium/Crawlee installed.
        from crawlee import ConcurrencySettings
        from crawlee.crawlers import PlaywrightCrawler
        from crawlee.storage_clients import MemoryStorageClient

        by_url = {
            _canonical_url(item.url): item
            for item in candidates
        }
        results: dict[str, BrowserVerificationResult] = {}

        crawler = PlaywrightCrawler(
            browser_type="chromium",
            headless=True,
            storage_client=MemoryStorageClient(),
            max_requests_per_crawl=len(candidates),
            max_request_retries=1,
            retry_on_blocked=False,
            use_session_pool=True,
            configure_logging=False,
            navigation_timeout=timedelta(seconds=max(3.0, navigation_timeout)),
            request_handler_timeout=timedelta(
                seconds=max(6.0, navigation_timeout + 4.0)
            ),
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1,
                desired_concurrency=max(1, min(2, max_concurrency)),
                max_concurrency=max(1, min(4, max_concurrency)),
            ),
            browser_new_context_options={
                "ignore_https_errors": False,
                "java_script_enabled": True,
                "locale": "en-US",
                "viewport": {"width": 1280, "height": 900},
            },
        )

        @crawler.pre_navigation_hook
        async def _before_navigation(context) -> None:
            # Guard every browser HTTP(S) request. This prevents a public URL
            # from redirecting the verifier into localhost/private literal IPs.
            # Static media/styles are skipped to keep the browser pass bounded;
            # JavaScript/XHR remain enabled because SPAs need them.
            async def _route_guard(route, request) -> None:
                request_url = str(request.url or "")
                scheme = urlsplit(request_url).scheme.casefold()
                if scheme in {"http", "https"}:
                    safe_url, _reason = _safe_public_url(request_url)
                    if not safe_url:
                        await route.abort()
                        return
                if str(request.resource_type or "").casefold() in {
                    "image", "media", "font", "stylesheet"
                }:
                    await route.abort()
                    return
                await route.continue_()

            try:
                await context.page.route("**/*", _route_guard)
            except Exception:
                pass

        @crawler.router.default_handler
        async def _handle(context) -> None:
            request_url = str(context.request.url or "")
            candidate = by_url.get(_canonical_url(request_url))
            if candidate is None:
                # Crawlee may normalize a URL. Match by profile relation as a
                # conservative fallback rather than dropping the observation.
                candidate = next(
                    (
                        item for item in candidates
                        if _canonical_url(item.url) == _canonical_url(request_url)
                    ),
                    None,
                )
            if candidate is None:
                return

            page = context.page
            try:
                await page.wait_for_load_state(
                    "domcontentloaded",
                    timeout=int(max(2500, navigation_timeout * 1000)),
                )
            except Exception:
                pass
            try:
                await page.wait_for_load_state("networkidle", timeout=1800)
            except Exception:
                pass
            try:
                await page.wait_for_timeout(250)
            except Exception:
                pass

            response = getattr(context, "response", None)
            status_code = None
            try:
                status_code = int(response.status) if response is not None else None
            except Exception:
                status_code = None

            final_url = str(getattr(page, "url", "") or request_url)
            title = ""
            visible_text = ""
            canonical = ""
            meta: dict[str, str] = {}

            try:
                title = str(await page.title() or "")[:4000]
            except Exception:
                pass

            try:
                visible_text = str(
                    await page.locator("body").inner_text(timeout=2200)
                    or ""
                )[:100000]
            except Exception:
                pass

            try:
                locator = page.locator('link[rel~="canonical"]').first
                canonical = str(await locator.get_attribute("href") or "")[:2000]
                if canonical:
                    canonical = urljoin(final_url, canonical)
            except Exception:
                canonical = ""

            for selector, key in (
                ('meta[property="og:type"]', "og:type"),
                ('meta[property="profile:username"]', "profile:username"),
                ('meta[name="profile:username"]', "profile:username"),
                ('meta[name="twitter:creator"]', "twitter:creator"),
                ('meta[property="og:title"]', "og:title"),
            ):
                if key in meta:
                    continue
                try:
                    value = str(
                        await page.locator(selector).first.get_attribute("content")
                        or ""
                    ).strip()
                    if value:
                        meta[key] = value[:1000]
                except Exception:
                    pass

            result = assess_rendered_profile(
                candidate=candidate,
                status_code=status_code,
                final_url=final_url,
                title=title,
                visible_text=visible_text,
                canonical=canonical,
                meta=meta,
            )
            results[_canonical_url(candidate.url)] = result

        @crawler.failed_request_handler
        async def _failed(context, error) -> None:
            request_url = str(context.request.url or "")
            candidate = by_url.get(_canonical_url(request_url))
            if candidate is None:
                return
            results[_canonical_url(candidate.url)] = BrowserVerificationResult(
                status="blocked",
                reason=f"Browser navigation failed or was blocked: {error}",
                checked=True,
                final_url=request_url,
            )

        await crawler.run([item.url for item in candidates])

        # Crawlee can skip/abort a request under resource pressure. Keep those
        # rows as uncertain rather than turning missing browser output into
        # negative evidence.
        for candidate in candidates:
            key = _canonical_url(candidate.url)
            results.setdefault(
                key,
                BrowserVerificationResult(
                    status="uncertain",
                    reason=(
                        "Browser verifier produced no conclusive observation; "
                        "the provider-reported account is retained for review."
                    ),
                    checked=False,
                    final_url=candidate.url,
                ),
            )
        return results


def annotate_browser_account_validation(
    rows: Iterable[dict[str, Any]],
    *,
    verifier: BrowserAccountVerifier | None = None,
    max_browser_checks: int = 14,
    navigation_timeout: float = 10.0,
    max_concurrency: int = 3,
) -> tuple[list[dict[str, Any]], BrowserVerificationSummary]:
    """Promote/demote only ambiguous account observations using a browser."""

    copied = [dict(row) for row in rows if isinstance(row, dict)]
    candidates: list[BrowserProfileCandidate] = []

    for row in copied:
        if not _is_username_account_row(row):
            continue
        status = str(
            row.get("accountVerificationStatus") or ""
        ).strip().casefold()
        if status not in _BROWSER_REVIEW_STATUSES:
            continue
        url = _public_url(str(row.get("url") or ""))
        username = _username_for_row(row)
        if not url or not username:
            continue
        candidates.append(
            BrowserProfileCandidate(
                url=url,
                username=username,
                source=str(row.get("source") or ""),
                service=str(row.get("service") or ""),
                provider_corroboration=max(
                    1,
                    _safe_int(row.get("accountProviderCorroboration")),
                ),
            )
        )

    backend = verifier or BrowserAccountVerifier()
    results, summary = backend.verify(
        candidates,
        max_checks=max_browser_checks,
        navigation_timeout=navigation_timeout,
        max_concurrency=max_concurrency,
    )

    for row in copied:
        if not _is_username_account_row(row):
            continue
        url = _public_url(str(row.get("url") or ""))
        if not url:
            continue
        result = results.get(_canonical_url(url))
        if result is None:
            continue

        row.update(result.row_fields())

        current = str(
            row.get("accountVerificationStatus") or "reported"
        ).strip().casefold()
        if result.status in {
            "verified",
            "likely",
            "uncertain",
            "blocked",
            "invalid",
        }:
            row["accountVerificationStatus"] = result.status
            row["accountVerificationLabel"] = result.status.replace(
                "_", " "
            ).title()
            row["accountVerificationReason"] = result.reason
            row["accountVerificationChecked"] = bool(
                row.get("accountVerificationChecked")
                or result.checked
            )
            if result.http_status is not None:
                row["accountVerificationHttpStatus"] = result.http_status
            if result.final_url:
                row["accountVerificationFinalUrl"] = result.final_url
        elif result.status == "unavailable":
            # Keep the HTTP status if the optional browser stack is absent.
            row["accountVerificationStatus"] = current
            row["accountVerificationReason"] = (
                str(row.get("accountVerificationReason") or "")
                + " Browser verification is unavailable."
            ).strip()

    return copied, summary


def assess_rendered_profile(
    *,
    candidate: BrowserProfileCandidate,
    status_code: int | None,
    final_url: str,
    title: str,
    visible_text: str,
    canonical: str = "",
    meta: dict[str, str] | None = None,
) -> BrowserVerificationResult:
    """Classify rendered page evidence conservatively."""

    meta = meta or {}
    username = candidate.username
    code = int(status_code or 0)

    title_match = _bounded_username_occurrence(username, title)
    visible_match = _bounded_username_occurrence(username, visible_text)
    final_url_match = _username_url_relation(username, final_url)
    canonical_match = bool(
        canonical and _username_url_relation(username, canonical)
    )
    marker = _not_found_marker(
        " ".join(part for part in (title, visible_text) if part)
    )
    blocked_marker = _blocked_marker(
        " ".join(part for part in (title, visible_text[:10000]) if part)
    )

    if code in {404, 410}:
        return BrowserVerificationResult(
            status="invalid",
            reason=f"Rendered profile navigation returned HTTP {code}.",
            checked=True,
            final_url=final_url,
            http_status=code,
            title=title,
            username_seen=bool(title_match or visible_match),
            negative_signal=f"http_{code}",
        )

    if marker:
        return BrowserVerificationResult(
            status="invalid",
            reason="Rendered page explicitly reports that the user/profile is absent.",
            checked=True,
            final_url=final_url,
            http_status=code or None,
            title=title,
            username_seen=bool(title_match or visible_match),
            negative_signal=marker,
        )

    if code in {401, 403, 407, 429} or code >= 500 or blocked_marker:
        return BrowserVerificationResult(
            status="blocked",
            reason=(
                f"Browser verification was blocked"
                + (f" with HTTP {code}" if code else "")
                + (f": {blocked_marker}" if blocked_marker else ".")
            ),
            checked=True,
            final_url=final_url,
            http_status=code or None,
            title=title,
            username_seen=bool(title_match or visible_match),
            negative_signal=blocked_marker,
        )

    original_has_username = _username_url_relation(username, candidate.url)
    if (
        original_has_username
        and not final_url_match
        and not _looks_like_auth_wall(final_url)
        and 200 <= code < 400
        and not title_match
        and not visible_match
    ):
        return BrowserVerificationResult(
            status="invalid",
            reason=(
                "Rendered navigation redirected away from the searched username "
                "to a generic page."
            ),
            checked=True,
            final_url=final_url,
            http_status=code,
            title=title,
            username_seen=False,
            negative_signal="generic_redirect",
        )

    explicit_profile_username = _explicit_profile_username(meta, username)
    profile_type = str(meta.get("og:type") or "").casefold() in {
        "profile", "profilepage", "person",
    }
    profile_vocabulary = _profile_vocabulary_signal(visible_text)

    signals: list[str] = []
    score = 0.0
    if explicit_profile_username:
        signals.append("Rendered profile username metadata matches")
        score += 55.0
    if title_match:
        signals.append("Rendered title contains searched username")
        score += 28.0
    if visible_match:
        signals.append("Rendered visible text contains searched username")
        score += 24.0
    if canonical_match:
        signals.append("Rendered canonical URL contains searched username")
        score += 18.0
    if final_url_match:
        signals.append("Rendered final URL contains searched username")
        score += 12.0
    if profile_type:
        signals.append("Rendered OpenGraph type identifies a profile/person")
        score += 18.0
    if profile_vocabulary:
        signals.append("Rendered page contains profile-specific vocabulary")
        score += 14.0
    if candidate.provider_corroboration > 1:
        signals.append(
            f"{candidate.provider_corroboration} providers reported the same profile"
        )
        score += min(
            12.0,
            float(candidate.provider_corroboration - 1) * 6.0,
        )

    strong = bool(
        explicit_profile_username
        or (
            title_match
            and visible_match
            and (profile_type or profile_vocabulary)
        )
    )
    if strong and score >= 55.0:
        return BrowserVerificationResult(
            status="verified",
            reason=(
                "Rendered browser page contains multiple independent "
                "profile-specific signals for the searched username."
            ),
            checked=True,
            final_url=final_url,
            http_status=code or None,
            title=title,
            username_seen=True,
            evidence_score=min(100.0, score),
            evidence_signals=tuple(signals[:8]),
        )

    # A JavaScript-rendered SPA may expose the username only after the browser
    # executes its client code.  Treat this as LIKELY, not VERIFIED, when the
    # profile-shaped URL remains intact and there is no contradictory evidence.
    if (
        200 <= code < 400
        and final_url_match
        and (title_match or visible_match)
    ):
        return BrowserVerificationResult(
            status="likely",
            reason=(
                "Rendered page remains on the searched profile URL and exposes "
                "the username, but stronger profile-specific proof is absent."
            ),
            checked=True,
            final_url=final_url,
            http_status=code,
            title=title,
            username_seen=True,
            evidence_score=min(100.0, score),
            evidence_signals=tuple(signals[:8]),
        )

    if 200 <= code < 400:
        return BrowserVerificationResult(
            status="uncertain",
            reason=(
                "Rendered page is reachable but does not provide enough positive "
                "or negative evidence to determine account availability."
            ),
            checked=True,
            final_url=final_url,
            http_status=code,
            title=title,
            username_seen=bool(title_match or visible_match),
            evidence_score=min(100.0, score),
            evidence_signals=tuple(signals[:8]),
        )

    return BrowserVerificationResult(
        status="blocked",
        reason=f"Browser verification returned HTTP {code or 'unknown'}.",
        checked=True,
        final_url=final_url,
        http_status=code or None,
        title=title,
        username_seen=bool(title_match or visible_match),
        evidence_score=min(100.0, score),
        evidence_signals=tuple(signals[:8]),
    )


def _explicit_profile_username(meta: dict[str, str], username: str) -> bool:
    wanted = str(username or "").strip().lstrip("@").casefold()
    if not wanted:
        return False
    for key in ("profile:username", "profile:screen_name", "twitter:creator"):
        value = str(meta.get(key) or "").strip().lstrip("@").casefold()
        if value and value == wanted:
            return True
    return False


def _blocked_marker(text: str) -> str:
    material = re.sub(r"\s+", " ", str(text or "")).casefold()
    for marker in _BLOCK_MARKERS:
        if marker in material:
            return marker
    return ""


def _is_username_account_row(row: dict[str, Any]) -> bool:
    if _kind(row.get("seedType")) != "username":
        return False
    return is_account_candidate_type(row.get("type"))


def _canonical_url(value: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.casefold().rstrip("/")
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    return f"{parsed.scheme.casefold()}://{host}{path}"


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _kind(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().casefold(),
    ).strip("_")


def _run_async(coro):
    """Run a Crawlee coroutine from a synchronous desktop worker safely."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # If an async host ever calls this compatibility layer, execute Crawlee in
    # an isolated helper thread rather than nesting an event loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _summarize(
    results: dict[str, BrowserVerificationResult],
    *,
    available: bool,
    error: str = "",
) -> BrowserVerificationSummary:
    counts = {status: 0 for status in _BROWSER_FINAL_STATUSES}
    checked = 0
    for result in results.values():
        if result.checked:
            checked += 1
        if result.status in counts:
            counts[result.status] += 1
    return BrowserVerificationSummary(
        available=available,
        checked=checked,
        verified=counts["verified"],
        likely=counts["likely"],
        uncertain=counts["uncertain"],
        blocked=counts["blocked"],
        invalid=counts["invalid"],
        unavailable=counts["unavailable"],
        error=error,
    )
