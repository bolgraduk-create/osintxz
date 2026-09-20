"""R13.26a.1 — bounded public account/profile validation.

Provider tools such as Sherlock are discovery engines, not authorities.  A
provider-reported "claimed" result may be stale when a site's detection rules
change.  This module performs a conservative, bounded second look at public
profile URLs before the presentation layer treats them as healthy accounts.

Validation never deletes observations.  It only annotates them:
- verified: independent/live evidence supports the profile;
- reported: a provider reported it, but live proof is insufficient;
- unreachable: the public page could not be checked reliably;
- invalid: direct evidence says the profile/page is absent.

Raw observations remain available regardless of the status.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urljoin, urlsplit

import httpx

from app.application.identity_resolution import is_account_candidate_type


_ACCOUNT_STATUSES = {"verified", "reported", "unreachable", "invalid"}
_AUTH_PATHS = {
    "login", "signin", "sign-in", "auth", "oauth", "session", "sessions",
}
_STRONG_NOT_FOUND_PATTERNS = (
    r"\buser(?:name)?\s+(?:was\s+)?not\s+found\b",
    r"\bprofile\s+(?:was\s+)?not\s+found\b",
    r"\baccount\s+(?:was\s+)?not\s+found\b",
    r"\bno\s+such\s+(?:user|profile|account)\b",
    r"\bthis\s+(?:user|profile|account)\s+does\s+not\s+exist\b",
    r"\bthis\s+(?:user|profile|account)\s+doesn't\s+exist\b",
    r"\bcould(?:n't|\s+not)\s+find\s+(?:this\s+)?(?:user|profile|account)\b",
    r"\bthe\s+(?:user|profile|account)\s+you(?:'re|\s+are)\s+looking\s+for\s+does\s+not\s+exist\b",
    r"\bpage\s+does\s+not\s+exist\b",
    r"\bpage\s+doesn't\s+exist\b",
)


@dataclass(frozen=True, slots=True)
class ProfileFetchResult:
    status_code: int | None
    final_url: str
    body: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class AccountValidation:
    status: str
    reason: str
    checked: bool
    status_code: int | None = None
    final_url: str = ""
    username_seen: bool = False
    not_found_marker: str = ""

    def row_fields(self) -> dict[str, Any]:
        return {
            "accountVerificationStatus": self.status,
            "accountVerificationLabel": self.status.replace("_", " ").title(),
            "accountVerificationReason": self.reason,
            "accountVerificationChecked": self.checked,
            "accountVerificationHttpStatus": self.status_code,
            "accountVerificationFinalUrl": self.final_url,
            "accountVerificationUsernameSeen": self.username_seen,
            "accountVerificationNotFoundMarker": self.not_found_marker,
        }


@dataclass(frozen=True, slots=True)
class AccountValidationSummary:
    total: int
    verified: int
    reported: int
    unreachable: int
    invalid: int
    live_checks: int
    corroborated_without_fetch: int

    def to_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "verified": self.verified,
            "reported": self.reported,
            "unreachable": self.unreachable,
            "invalid": self.invalid,
            "liveChecks": self.live_checks,
            "corroboratedWithoutFetch": self.corroborated_without_fetch,
        }


FetchCallable = Callable[[str, float, int], ProfileFetchResult]


def annotate_account_profile_validation(
    rows: Iterable[dict[str, Any]],
    *,
    max_live_checks: int = 48,
    timeout: float = 4.0,
    max_body_bytes: int = 131072,
    workers: int = 8,
    fetcher: FetchCallable | None = None,
) -> tuple[list[dict[str, Any]], AccountValidationSummary]:
    """Annotate account observations while preserving every original row."""

    copied = [dict(row) for row in rows if isinstance(row, dict)]
    account_indexes: list[int] = []
    url_groups: dict[str, list[int]] = {}

    for index, row in enumerate(copied):
        if not _is_username_account_row(row):
            continue
        account_indexes.append(index)
        url = _public_url(str(row.get("url") or ""))
        if url:
            url_groups.setdefault(_canonical_url(url), []).append(index)

    validations: dict[int, AccountValidation] = {}
    live_candidates: list[tuple[str, list[int]]] = []
    corroborated_without_fetch = 0

    for index in account_indexes:
        row = copied[index]
        metadata = row.get("findingMetadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if _metadata_negative(metadata):
            validations[index] = AccountValidation(
                status="invalid",
                reason="Provider metadata explicitly reports the account as absent.",
                checked=False,
            )

    for canonical_url, indexes in url_groups.items():
        unresolved = [index for index in indexes if index not in validations]
        if not unresolved:
            continue
        sources = {
            str(copied[index].get("source") or "").strip().casefold()
            for index in unresolved
            if str(copied[index].get("source") or "").strip()
        }
        if len(sources) > 1:
            corroborated_without_fetch += 1
            validation = AccountValidation(
                status="verified",
                reason=f"Same profile URL was independently reported by {len(sources)} sources.",
                checked=False,
                final_url=str(copied[unresolved[0]].get("url") or ""),
            )
            for index in unresolved:
                validations[index] = validation
            continue
        live_candidates.append((canonical_url, unresolved))

    # Rows with no URL remain useful provider observations, but are not verified.
    for index in account_indexes:
        if index in validations:
            continue
        if not _public_url(str(copied[index].get("url") or "")):
            validations[index] = AccountValidation(
                status="reported",
                reason="Provider reported the account but did not expose a public profile URL.",
                checked=False,
            )

    # Prefer checking Sherlock-only observations first because its site rules are
    # the main source of stale/generic positive pages seen in the current UI.
    live_candidates.sort(
        key=lambda item: (
            0 if any(
                str(copied[index].get("source") or "").strip().casefold() == "sherlock"
                for index in item[1]
            ) else 1,
            item[0],
        )
    )

    selected = live_candidates[: max(0, int(max_live_checks))]
    skipped = live_candidates[len(selected):]
    fetch = fetcher or _fetch_public_profile

    if selected:
        with ThreadPoolExecutor(max_workers=max(1, min(int(workers), len(selected)))) as pool:
            futures = {}
            for _canonical, indexes in selected:
                row = copied[indexes[0]]
                url = str(row.get("url") or "")
                username = _username_for_row(row)
                future = pool.submit(
                    _validate_one_url,
                    url,
                    username,
                    timeout,
                    max_body_bytes,
                    fetch,
                )
                futures[future] = indexes

            for future in as_completed(futures):
                indexes = futures[future]
                try:
                    validation = future.result()
                except Exception as exc:  # defensive: validation must not break search
                    validation = AccountValidation(
                        status="unreachable",
                        reason=f"Profile validation failed safely: {type(exc).__name__}: {exc}",
                        checked=True,
                    )
                for index in indexes:
                    validations[index] = validation

    for _canonical, indexes in skipped:
        validation = AccountValidation(
            status="reported",
            reason="Provider-reported account was retained; live verification budget was exhausted.",
            checked=False,
        )
        for index in indexes:
            validations[index] = validation

    for index in account_indexes:
        validation = validations.get(index)
        if validation is None:
            validation = AccountValidation(
                status="reported",
                reason="Provider-reported account has not been independently verified.",
                checked=False,
            )
        copied[index].update(validation.row_fields())

    status_counts = {status: 0 for status in _ACCOUNT_STATUSES}
    for index in account_indexes:
        status = str(copied[index].get("accountVerificationStatus") or "reported")
        if status in status_counts:
            status_counts[status] += 1

    return (
        copied,
        AccountValidationSummary(
            total=len(account_indexes),
            verified=status_counts["verified"],
            reported=status_counts["reported"],
            unreachable=status_counts["unreachable"],
            invalid=status_counts["invalid"],
            live_checks=len(selected),
            corroborated_without_fetch=corroborated_without_fetch,
        ),
    )


def _validate_one_url(
    url: str,
    username: str,
    timeout: float,
    max_body_bytes: int,
    fetcher: FetchCallable,
) -> AccountValidation:
    safe_url, blocked_reason = _safe_public_url(url)
    if not safe_url:
        return AccountValidation(
            status="unreachable",
            reason=blocked_reason or "Profile URL is not a supported public HTTP(S) URL.",
            checked=False,
        )

    result = fetcher(safe_url, timeout, max_body_bytes)
    if result.error:
        return AccountValidation(
            status="unreachable",
            reason=f"Live profile check could not complete: {result.error}",
            checked=True,
            status_code=result.status_code,
            final_url=result.final_url,
        )

    code = int(result.status_code or 0)
    final_url = result.final_url or safe_url
    body = str(result.body or "")
    username_seen = _bounded_username_occurrence(username, body)
    marker = _not_found_marker(body)

    if code in {404, 410}:
        return AccountValidation(
            status="invalid",
            reason=f"Profile URL returned HTTP {code}.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=username_seen,
            not_found_marker=marker,
        )

    if code in {401, 403, 407, 429} or code >= 500:
        return AccountValidation(
            status="unreachable",
            reason=f"Profile could not be independently verified because the site returned HTTP {code}.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=username_seen,
            not_found_marker=marker,
        )

    if marker and not username_seen:
        return AccountValidation(
            status="invalid",
            reason="Profile page contains a strong not-found/account-absent marker.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=False,
            not_found_marker=marker,
        )

    original_has_username = _username_url_relation(username, safe_url)
    final_has_username = _username_url_relation(username, final_url)
    if (
        original_has_username
        and not final_has_username
        and not _looks_like_auth_wall(final_url)
        and 200 <= code < 400
        and not username_seen
    ):
        return AccountValidation(
            status="invalid",
            reason="Profile URL redirected away from the searched username to a generic page.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=False,
        )

    if 200 <= code < 400 and username_seen and (final_has_username or original_has_username):
        return AccountValidation(
            status="verified",
            reason="Live profile page is reachable and contains the searched username.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=True,
        )

    if 200 <= code < 400:
        return AccountValidation(
            status="reported",
            reason="Profile URL is reachable, but the response does not independently prove that the account exists.",
            checked=True,
            status_code=code,
            final_url=final_url,
            username_seen=username_seen,
            not_found_marker=marker,
        )

    return AccountValidation(
        status="unreachable",
        reason=f"Profile check returned HTTP {code or 'unknown'}.",
        checked=True,
        status_code=code or None,
        final_url=final_url,
        username_seen=username_seen,
        not_found_marker=marker,
    )


def _fetch_public_profile(
    url: str,
    timeout: float,
    max_body_bytes: int,
) -> ProfileFetchResult:
    headers = {
        "User-Agent": "OSINTXZ/1.0 public-profile-validation",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
    }
    try:
        current_url = url
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(float(timeout)),
            headers=headers,
        ) as client:
            for _hop in range(6):
                safe_current, blocked_reason = _safe_public_url(current_url)
                if not safe_current:
                    return ProfileFetchResult(
                        status_code=None,
                        final_url=current_url,
                        body="",
                        error=blocked_reason or "Redirect target is not a safe public URL.",
                    )

                with client.stream("GET", safe_current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = str(response.headers.get("location") or "").strip()
                        if not location:
                            return ProfileFetchResult(
                                status_code=response.status_code,
                                final_url=str(response.url),
                                body="",
                            )
                        next_url = urljoin(str(response.url), location)
                        safe_next, blocked_reason = _safe_public_url(next_url)
                        if not safe_next:
                            return ProfileFetchResult(
                                status_code=response.status_code,
                                final_url=next_url,
                                body="",
                                error=blocked_reason or "Redirect target is not a safe public URL.",
                            )
                        current_url = safe_next
                        continue

                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        if not chunk:
                            continue
                        remaining = max_body_bytes - size
                        if remaining <= 0:
                            break
                        piece = chunk[:remaining]
                        chunks.append(piece)
                        size += len(piece)
                        if size >= max_body_bytes:
                            break
                    raw = b"".join(chunks)
                    encoding = response.encoding or "utf-8"
                    try:
                        body = raw.decode(encoding, errors="replace")
                    except LookupError:
                        body = raw.decode("utf-8", errors="replace")
                    return ProfileFetchResult(
                        status_code=response.status_code,
                        final_url=str(response.url),
                        body=body,
                    )

            return ProfileFetchResult(
                status_code=None,
                final_url=current_url,
                body="",
                error="Too many redirects during profile validation.",
            )
    except Exception as exc:
        return ProfileFetchResult(
            status_code=None,
            final_url="",
            body="",
            error=f"{type(exc).__name__}: {exc}",
        )


def _is_username_account_row(row: dict[str, Any]) -> bool:
    seed_type = _kind(row.get("seedType"))
    if seed_type != "username":
        return False
    return is_account_candidate_type(row.get("type"))


def _username_for_row(row: dict[str, Any]) -> str:
    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict):
        for key in ("username", "handle", "login", "user_name"):
            value = str(identifiers.get(key) or "").strip().lstrip("@")
            if value:
                return value
    seed = str(row.get("seed") or "").strip().lstrip("@")
    if seed:
        return seed
    return str(row.get("title") or "").strip().lstrip("@")


def _metadata_negative(metadata: dict[str, Any]) -> bool:
    if metadata.get("available") is True:
        return True
    for key in ("exists", "claimed", "registered", "used"):
        if key in metadata and metadata.get(key) is False:
            return True
    status = str(
        metadata.get("status")
        or metadata.get("state")
        or metadata.get("result")
        or ""
    ).strip().casefold()
    return status in {
        "available", "free", "not found", "not_found", "missing", "unclaimed",
        "false", "absent",
    }


def _public_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    return raw if parsed.hostname else ""


def _safe_public_url(value: str) -> tuple[str, str]:
    raw = _public_url(value)
    if not raw:
        return "", "Profile URL is not a valid public HTTP(S) URL."
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "", "Profile URL is invalid."

    host = (parsed.hostname or "").strip().casefold().rstrip(".")
    if not host:
        return "", "Profile URL has no hostname."
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return "", "Local/private profile URLs are not fetched."

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return "", "Private/reserved profile URLs are not fetched."

    return raw, ""


def _canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        return str(value or "").strip().casefold()
    host = (parsed.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
    query = "&".join(
        f"{key}={val}"
        for key, val in sorted(parse_qsl(parsed.query, keep_blank_values=True))
        if not key.casefold().startswith("utm_")
    )
    return f"{parsed.scheme.casefold()}://{host}{path}" + (f"?{query}" if query else "")


def _username_url_relation(username: str, value: str) -> bool:
    wanted = str(username or "").strip().lstrip("@").casefold()
    if not wanted:
        return False
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return False

    host_parts = (parsed.hostname or "").casefold().split(".")
    if host_parts and host_parts[0] == wanted:
        return True

    segments = [segment.casefold().lstrip("@") for segment in parsed.path.split("/") if segment]
    if wanted in segments:
        return True

    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        if wanted in {str(key).casefold().lstrip("@"), str(val).casefold().lstrip("@")}:
            return True
    return False


def _bounded_username_occurrence(username: str, body: str) -> bool:
    wanted = str(username or "").strip().lstrip("@")
    if not wanted:
        return False
    pattern = rf"(?<![A-Za-z0-9_.-])@?{re.escape(wanted)}(?![A-Za-z0-9_.-])"
    return re.search(pattern, str(body or ""), flags=re.IGNORECASE) is not None


def _not_found_marker(body: str) -> str:
    text = re.sub(r"\s+", " ", str(body or "")).casefold()
    for pattern in _STRONG_NOT_FOUND_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)[:160]
    return ""


def _looks_like_auth_wall(value: str) -> bool:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return False
    segments = [segment.casefold() for segment in parsed.path.split("/") if segment]
    return bool(segments and segments[0] in _AUTH_PATHS)


def _kind(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        str(value or "").strip().casefold(),
    ).strip("_")
