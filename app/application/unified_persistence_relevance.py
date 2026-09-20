"""R13.21.2 pre-persistence relevance gate for Unified Investigation Search.

This gate is intentionally strict and is enabled only by the unified live-search
worker.  Existing OSINT workflows keep their historical persistence behaviour.
The gate never asserts identity; it only asks whether a finding contains enough
proof that it belongs to the exact target currently being enriched.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.osint.models import OsintTargetType


_SECRET_KEYS = (
    "password", "passwd", "secret", "token", "cookie", "session",
    "authorization", "private_key", "credential",
)


class UnifiedFindingPersistenceGate:
    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = dict(profile or {})

    def __call__(
        self,
        *,
        target_type: OsintTargetType,
        target_value: str,
        goal: Any,
        connector: str,
        finding: Any,
    ) -> bool:
        del goal, connector
        value = str(getattr(finding, "value", "") or "")
        url = str(getattr(finding, "url", "") or "")
        metadata = getattr(finding, "metadata", None)
        material = _bounded_material(metadata)

        if target_type is OsintTargetType.USERNAME:
            if _username_persistence_blocked(metadata):
                return False
            wanted = _username(target_value)
            if not wanted:
                return False
            return any(
                _username_equals(wanted, candidate)
                for candidate in _username_candidates(value, url, material)
            )

        if target_type is OsintTargetType.EMAIL:
            wanted = _email(target_value)
            return bool(wanted and wanted in _email_candidates(value, url, material))

        if target_type is OsintTargetType.PHONE:
            wanted = _phone(target_value)
            return bool(wanted and wanted in _phone_candidates(value, material))

        if target_type is OsintTargetType.DOMAIN:
            wanted = _domain(target_value)
            if not wanted:
                return False
            candidates = _domain_candidates(value, url, material)
            return any(item == wanted or item.endswith("." + wanted) for item in candidates)

        if target_type is OsintTargetType.URL:
            wanted = _url(target_value)
            if not wanted:
                return False
            candidates = {_url(value), _url(url)}
            candidates.update(_urls_from_text(material))
            return wanted in {item for item in candidates if item}

        if target_type is OsintTargetType.IP:
            wanted = _ip(target_value)
            return bool(wanted and wanted in _ip_candidates(value, material))

        if target_type is OsintTargetType.HASH:
            wanted = _compact(target_value)
            candidates = {_compact(value)} | {_compact(x) for x in re.findall(r"\b[a-fA-F0-9]{32,128}\b", material)}
            return bool(wanted and wanted in candidates)

        # PERSON/ORGANIZATION/LOCATION/FILE/IMAGE have no automatic classic
        # persistence route in the unified search plan. Keep compatibility if
        # one is introduced later rather than silently blocking it here.
        return True


def build_unified_finding_gate(profile: dict[str, Any] | None = None) -> UnifiedFindingPersistenceGate:
    return UnifiedFindingPersistenceGate(profile)


def _username_persistence_blocked(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    status = str(metadata.get("account_verification_status") or "").strip().casefold()
    if status == "invalid":
        return True
    if metadata.get("requires_account_verification") is True:
        return metadata.get("registration_confirmed") is not True
    return False


def _bounded_material(value: Any, *, depth: int = 0) -> str:
    if value is None or depth > 3:
        return ""
    if isinstance(value, dict):
        parts: list[str] = []
        for index, (key, child) in enumerate(value.items()):
            if index >= 80:
                break
            normalized = str(key or "").casefold()
            if any(marker in normalized for marker in _SECRET_KEYS):
                continue
            part = _bounded_material(child, depth=depth + 1)
            if part:
                parts.append(part)
        return " ".join(parts)[:16000]
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(_bounded_material(x, depth=depth + 1) for x in list(value)[:60])[:16000]
    return str(value or "").strip()[:2000]


def _username(value: Any) -> str:
    return str(value or "").strip().lstrip("@").casefold()


def _username_equals(wanted: str, candidate: str) -> bool:
    return bool(wanted and candidate and wanted == _username(candidate))


def _username_candidates(value: str, url: str, material: str) -> set[str]:
    out: set[str] = set()
    raw = str(value or "").strip()
    if re.fullmatch(r"@?[A-Za-z0-9_.-]{2,64}", raw):
        out.add(_username(raw))
    for source in (value, url, material):
        for match in re.findall(r"(?<![A-Za-z0-9_.-])@([A-Za-z0-9_.-]{2,64})", str(source or "")):
            out.add(_username(match))
        for found_url in re.findall(r"https?://[^\s<>\"]+", str(source or "")):
            owner = _username_from_account_url(found_url)
            if owner:
                out.add(owner)
    return out


def _username_from_account_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    segments = [seg for seg in parsed.path.split("/") if seg]
    if not segments:
        return ""
    first = _username(segments[0])
    if first and re.fullmatch(r"[a-z0-9_.-]{2,64}", first):
        return first
    namespaces = {"user", "users", "u", "profile", "profiles", "people", "member", "members"}
    if len(segments) >= 2 and segments[0].casefold() in namespaces:
        second = _username(segments[1])
        if second and re.fullmatch(r"[a-z0-9_.-]{2,64}", second):
            return second
    return ""


def _email(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    return raw if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw) else ""


def _email_candidates(*values: str) -> set[str]:
    out: set[str] = set()
    for value in values:
        direct = _email(value)
        if direct:
            out.add(direct)
        for match in re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", str(value or "")):
            normalized = _email(match)
            if normalized:
                out.add(normalized)
    return out


def _phone(value: Any) -> str:
    raw = str(value or "").strip()
    prefix = "+" if raw.startswith("+") else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return prefix + digits if len(digits) >= 6 else ""


def _phone_candidates(*values: str) -> set[str]:
    out: set[str] = set()
    for value in values:
        direct = _phone(value)
        if direct:
            out.add(direct)
        for match in re.findall(r"\+?[0-9][0-9()\-\s]{5,24}[0-9]", str(value or "")):
            normalized = _phone(match)
            if normalized:
                out.add(normalized)
    return out


def _domain(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if not raw:
        return ""
    if "://" in raw:
        try:
            raw = urlsplit(raw).hostname or ""
        except ValueError:
            return ""
    raw = raw.split("/", 1)[0].split(":", 1)[0].rstrip(".")
    if raw.startswith("www."):
        raw = raw[4:]
    return raw if "." in raw else ""


def _domain_candidates(value: str, url: str, material: str) -> set[str]:
    out: set[str] = set()
    for raw in (value, url):
        domain = _domain(raw)
        if domain:
            out.add(domain)
    for host in re.findall(r"(?<![@\w-])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}", material):
        domain = _domain(host)
        if domain:
            out.add(domain)
    for found_url in re.findall(r"https?://[^\s<>\"]+", material):
        domain = _domain(found_url)
        if domain:
            out.add(domain)
    return out


def _url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if not parsed.hostname:
        return ""
    host = parsed.hostname.casefold().rstrip(".")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not k.casefold().startswith("utm_")]
    return urlunsplit((parsed.scheme.casefold(), host + port, path, urlencode(query), ""))


def _urls_from_text(value: str) -> set[str]:
    return {_url(x) for x in re.findall(r"https?://[^\s<>\"]+", str(value or "")) if _url(x)}


def _ip(value: Any) -> str:
    try:
        return str(ipaddress.ip_address(str(value or "").strip()))
    except ValueError:
        return ""


def _ip_candidates(*values: str) -> set[str]:
    out: set[str] = set()
    for value in values:
        direct = _ip(value)
        if direct:
            out.add(direct)
        for token in re.findall(r"(?<![0-9A-Fa-f:.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9A-Fa-f:.])", str(value or "")):
            normalized = _ip(token)
            if normalized:
                out.add(normalized)
    return out


def _compact(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).casefold()
