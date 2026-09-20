"""R13.20 — policy-aware planning for one structured investigation search.

This module is deliberately pure: it performs no network I/O, no database I/O,
and no Qt work.  It converts analyst-supplied known data into typed seeds,
selects safe Federation capabilities, constructs Registry queries, and extracts
bounded exact-identifier pivots from normalized remote records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from app.osint.models import OsintTargetType
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryQuery,
    RegistryQueryKind,
)


class UnifiedSeedKind(str, Enum):
    PERSON_NAME = "person_name"
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    ORGANIZATION = "organization"
    REGISTRATION_ID = "registration_id"
    VAT_ID = "vat_id"
    LEI = "lei"
    DOMAIN = "domain"
    URL = "url"
    IP = "ip"
    ASN = "asn"
    HASH = "hash"
    ORCID = "orcid"
    NPI = "npi"
    CVE = "cve"
    DOI = "doi"
    CASE_NUMBER = "case_number"
    CRYPTO_ADDRESS = "crypto_address"
    REPOSITORY = "repository"
    KEYWORD = "keyword"


@dataclass(frozen=True, slots=True)
class UnifiedSeed:
    kind: UnifiedSeedKind
    value: str
    origin: str = "user"
    depth: int = 0
    country: str | None = None
    parent_ref: str | None = None
    candidate_only: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        value = str(self.value or "").strip()
        if not value:
            raise ValueError("Unified seed value must not be empty.")
        object.__setattr__(self, "value", value)
        if self.depth < 0:
            raise ValueError("Unified seed depth must not be negative.")
        if self.country:
            code = str(self.country).strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise ValueError("Seed country must be ISO alpha-2.")
            object.__setattr__(self, "country", code)

    @property
    def identity_key(self) -> tuple[str, str, str]:
        return (
            self.kind.value,
            _normalize_value(self.kind, self.value),
            self.country or "",
        )


@dataclass(frozen=True, slots=True)
class FederationRoute:
    source_code: str
    capability: str
    automatic: bool
    configured: bool
    reason: str = ""


@dataclass(slots=True)
class UnifiedSearchPlan:
    seeds: list[UnifiedSeed] = field(default_factory=list)
    classic_seeds: list[UnifiedSeed] = field(default_factory=list)
    open_web_seeds: list[UnifiedSeed] = field(default_factory=list)
    federation_routes: list[tuple[UnifiedSeed, FederationRoute]] = field(default_factory=list)
    registry_queries: list[tuple[UnifiedSeed, RegistryQuery]] = field(default_factory=list)
    guarded_routes: list[tuple[UnifiedSeed, FederationRoute]] = field(default_factory=list)


_SECRET_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "session",
    "authorization",
    "private_key",
    "privatekey",
    "credential",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_.-]{2,100}$")
_DOMAIN_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
_PHONE_RE = re.compile(r"^\+?[0-9][0-9()\-\s]{5,28}$")
_HASH_RE = re.compile(r"^[A-Fa-f0-9]{32,128}$")
_CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-[\dX]{4}$", re.IGNORECASE)
_NPI_RE = re.compile(r"^\d{10}$")
_LEI_RE = re.compile(r"^[A-Z0-9]{20}$", re.IGNORECASE)
_ASN_RE = re.compile(r"^(?:AS)?\d{1,10}$", re.IGNORECASE)
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


_MULTI_FIELDS: tuple[tuple[str, UnifiedSeedKind], ...] = (
    ("aliases", UnifiedSeedKind.PERSON_NAME),
    ("usernames", UnifiedSeedKind.USERNAME),
    ("emails", UnifiedSeedKind.EMAIL),
    ("phones", UnifiedSeedKind.PHONE),
    ("organizations", UnifiedSeedKind.ORGANIZATION),
    ("registrationIds", UnifiedSeedKind.REGISTRATION_ID),
    ("vatIds", UnifiedSeedKind.VAT_ID),
    ("leis", UnifiedSeedKind.LEI),
    ("domains", UnifiedSeedKind.DOMAIN),
    ("urls", UnifiedSeedKind.URL),
    ("ips", UnifiedSeedKind.IP),
    ("asns", UnifiedSeedKind.ASN),
    ("hashes", UnifiedSeedKind.HASH),
    ("orcids", UnifiedSeedKind.ORCID),
    ("npis", UnifiedSeedKind.NPI),
    ("cves", UnifiedSeedKind.CVE),
    ("dois", UnifiedSeedKind.DOI),
    ("caseNumbers", UnifiedSeedKind.CASE_NUMBER),
    ("cryptoAddresses", UnifiedSeedKind.CRYPTO_ADDRESS),
    ("repositories", UnifiedSeedKind.REPOSITORY),
    ("keywords", UnifiedSeedKind.KEYWORD),
)


_EXACT_PIVOT_KINDS = frozenset(
    {
        UnifiedSeedKind.USERNAME,
        UnifiedSeedKind.EMAIL,
        UnifiedSeedKind.PHONE,
        UnifiedSeedKind.REGISTRATION_ID,
        UnifiedSeedKind.VAT_ID,
        UnifiedSeedKind.LEI,
        UnifiedSeedKind.DOMAIN,
        UnifiedSeedKind.URL,
        UnifiedSeedKind.IP,
        UnifiedSeedKind.ASN,
        UnifiedSeedKind.HASH,
        UnifiedSeedKind.ORCID,
        UnifiedSeedKind.NPI,
        UnifiedSeedKind.CVE,
        UnifiedSeedKind.DOI,
        UnifiedSeedKind.CASE_NUMBER,
        UnifiedSeedKind.CRYPTO_ADDRESS,
        UnifiedSeedKind.REPOSITORY,
    }
)


_OSINT_TARGETS: dict[UnifiedSeedKind, OsintTargetType] = {
    UnifiedSeedKind.USERNAME: OsintTargetType.USERNAME,
    UnifiedSeedKind.EMAIL: OsintTargetType.EMAIL,
    UnifiedSeedKind.PHONE: OsintTargetType.PHONE,
    UnifiedSeedKind.DOMAIN: OsintTargetType.DOMAIN,
    UnifiedSeedKind.URL: OsintTargetType.URL,
    UnifiedSeedKind.IP: OsintTargetType.IP,
    UnifiedSeedKind.HASH: OsintTargetType.HASH,
    UnifiedSeedKind.PERSON_NAME: OsintTargetType.PERSON,
    UnifiedSeedKind.ORGANIZATION: OsintTargetType.ORGANIZATION,
    UnifiedSeedKind.ADDRESS: OsintTargetType.LOCATION,
}


# Priority is intentional: one safe automatic route per adapter/seed keeps one
# source from running repeatedly under several synonymous capabilities.
_GUARDED_CAPABILITY_PRIORITIES: dict[UnifiedSeedKind, tuple[str, ...]] = {
    UnifiedSeedKind.PERSON_NAME: (
        "wanted_name", "wanted_person", "sanctions_name", "sanctions_entity", "un_sanctions"
    ),
    UnifiedSeedKind.ORGANIZATION: ("sanctions_entity", "sanctions_name", "un_sanctions"),
    UnifiedSeedKind.EMAIL: (
        "breach_lookup", "paste_exposure", "stealer_log_email"
    ),
    UnifiedSeedKind.DOMAIN: (
        "verified_domain_breach", "domain_exposure", "stealer_log_email_domain",
        "stealer_log_website_domain", "darkweb_index"
    ),
    UnifiedSeedKind.REPOSITORY: ("repository_secret_exposure",),
    UnifiedSeedKind.URL: ("darkweb_index", "public_page_observation"),
    UnifiedSeedKind.IP: ("darkweb_index",),
    UnifiedSeedKind.PHONE: ("darkweb_index",),
    UnifiedSeedKind.CRYPTO_ADDRESS: ("darkweb_index",),
}


_CAPABILITY_PRIORITIES: dict[UnifiedSeedKind, tuple[str, ...]] = {
    UnifiedSeedKind.PERSON_NAME: (
        # Person-name searches must use semantically person/author-aware
        # capabilities. Generic archive/keyword search is intentionally not
        # automatic here because token-OR upstreams can return unrelated
        # names (for example a shared first name or surname). Analysts can
        # still search those sources explicitly with the Keyword field.
        "name", "person", "author", "academic_author"
    ),
    UnifiedSeedKind.USERNAME: ("username", "github_username", "gitlab_username"),
    UnifiedSeedKind.EMAIL: ("email",),
    UnifiedSeedKind.PHONE: ("phone",),
    UnifiedSeedKind.ADDRESS: ("address", "location"),
    UnifiedSeedKind.ORGANIZATION: (
        # Organization seeds only use organization-aware capabilities. Generic
        # name/archive/keyword routes create token-OR noise (for example every
        # entity containing only the word "Foundation").
        "organization", "recipient", "federal_award_recipient", "company",
        "legal_entity"
    ),
    UnifiedSeedKind.REGISTRATION_ID: (
        "registration_id", "organization_number", "company_number", "uei", "duns"
    ),
    UnifiedSeedKind.VAT_ID: ("vat_id", "vat"),
    UnifiedSeedKind.LEI: ("lei",),
    UnifiedSeedKind.DOMAIN: (
        "domain", "domain_rdap", "domain_dns", "dns", "network_registration"
    ),
    UnifiedSeedKind.URL: ("url", "historical_web", "archive_search"),
    UnifiedSeedKind.IP: ("ip", "ip_address", "network_registration", "open_ports"),
    UnifiedSeedKind.ASN: ("asn", "autonomous_system", "peering_network"),
    UnifiedSeedKind.HASH: ("hash", "sha256", "sha1", "md5"),
    UnifiedSeedKind.ORCID: ("orcid",),
    UnifiedSeedKind.NPI: ("npi", "npi_number"),
    UnifiedSeedKind.CVE: ("cve", "cve_id", "known_exploited", "epss"),
    UnifiedSeedKind.DOI: ("doi", "publication", "research_output"),
    UnifiedSeedKind.CASE_NUMBER: ("case_number",),
    UnifiedSeedKind.CRYPTO_ADDRESS: ("crypto_address", "bitcoin", "ethereum"),
    UnifiedSeedKind.REPOSITORY: ("repository", "repo", "github_repository"),
    UnifiedSeedKind.KEYWORD: ("keyword", "archive_search", "publication", "research_output"),
}


# Name-driven sensitive routes remain visible in Source Center but are not
# launched as generic pivots. Exact case numbers stay allowed separately.
_GUARDED_CAPABILITY_MARKERS = (
    "wanted",
    "sanction",
    "stealer",
    "secret_scanning",
    "repository_secret",
    "verified_domain",
    "darkweb",
    "onion",
)


def split_values(value: Any) -> list[str]:
    """Parse a multi-value UI field without breaking ordinary postal addresses."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        raw_items = [str(item) for item in value]
    else:
        text = str(value).replace("\r", "\n")
        raw_items = []
        for line in text.split("\n"):
            raw_items.extend(line.split(";"))
    out: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        item = " ".join(str(raw).strip().split())
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def build_initial_seeds(payload: dict[str, Any]) -> list[UnifiedSeed]:
    """Convert the Investigation Search form into typed, deduplicated seeds."""
    country = _country(payload.get("country"))
    metadata = {
        "birth_date": str(payload.get("birthDate") or "").strip(),
        "region": str(payload.get("region") or "").strip(),
        "city": str(payload.get("city") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
    }

    seeds: list[UnifiedSeed] = []
    first = str(payload.get("firstName") or "").strip()
    middle = str(payload.get("middleName") or "").strip()
    last = str(payload.get("lastName") or "").strip()
    full_name = " ".join(part for part in (first, middle, last) if part)
    if full_name:
        seeds.append(
            UnifiedSeed(
                UnifiedSeedKind.PERSON_NAME,
                full_name,
                country=country,
                metadata={**metadata, "primary_name": True},
            )
        )

    for field_name, kind in _MULTI_FIELDS:
        for value in split_values(payload.get(field_name)):
            seeds.append(
                UnifiedSeed(
                    kind,
                    value,
                    country=country,
                    candidate_only=(field_name == "aliases"),
                    metadata={**metadata, "field": field_name},
                )
            )

    address_parts = [
        str(payload.get("address") or "").strip(),
        str(payload.get("city") or "").strip(),
        str(payload.get("region") or "").strip(),
        str(payload.get("postalCode") or "").strip(),
        country or "",
    ]
    if any(address_parts[:-1]):
        seeds.append(
            UnifiedSeed(
                UnifiedSeedKind.ADDRESS,
                ", ".join(part for part in address_parts if part),
                country=country,
                metadata=metadata,
            )
        )

    return dedupe_seeds(seeds)


def dedupe_seeds(seeds: Iterable[UnifiedSeed]) -> list[UnifiedSeed]:
    out: list[UnifiedSeed] = []
    seen: set[tuple[str, str, str]] = set()
    for seed in seeds:
        if seed.identity_key in seen:
            continue
        seen.add(seed.identity_key)
        out.append(seed)
    return out


def osint_target_for_seed(seed: UnifiedSeed) -> OsintTargetType | None:
    return _OSINT_TARGETS.get(seed.kind)


def is_exact_recursive_seed(seed: UnifiedSeed) -> bool:
    return seed.kind in _EXACT_PIVOT_KINDS and not seed.candidate_only


def plan_federation_routes(adapter_registry: Any, seed: UnifiedSeed) -> tuple[list[FederationRoute], list[FederationRoute]]:
    """Plan at most one semantically relevant capability per adapter.

    Automatic routes may be executed by the unified search. Nonautomatic
    routes remain visible as guarded so contract/verified/dark-web sources are
    never pulled in merely because a generic investigation was started.
    """
    priorities = _CAPABILITY_PRIORITIES.get(seed.kind, ())
    if not priorities:
        return [], []

    automatic: list[FederationRoute] = []
    guarded: list[FederationRoute] = []
    for adapter in tuple(adapter_registry.all()):
        capabilities = {str(item).strip().casefold() for item in adapter.capabilities}
        capability = next((item for item in priorities if item in capabilities), None)
        guarded_priority = _GUARDED_CAPABILITY_PRIORITIES.get(seed.kind, ())
        guarded_capability = next(
            (item for item in guarded_priority if item in capabilities),
            None,
        )
        if capability is None and guarded_capability is None:
            continue
        if capability is None:
            capability = guarded_capability
        if (
            guarded_capability == capability
            or any(marker in capability for marker in _GUARDED_CAPABILITY_MARKERS)
        ):
            guarded.append(
                FederationRoute(
                    source_code=adapter.source_code,
                    capability=capability,
                    automatic=False,
                    configured=bool(adapter.configured),
                    reason="Sensitive/verified source requires explicit execution.",
                )
            )
            continue
        if seed.country and not adapter.global_scope and seed.country not in adapter.countries:
            continue
        route = FederationRoute(
            source_code=adapter.source_code,
            capability=capability,
            automatic=bool(adapter.automatic_enabled),
            configured=bool(adapter.configured),
            reason=("" if adapter.automatic_enabled else "Source opted out of automatic execution."),
        )
        (automatic if route.automatic else guarded).append(route)

    automatic.sort(key=lambda item: item.source_code)
    guarded.sort(key=lambda item: item.source_code)
    return automatic, guarded


def registry_queries_for_seed(
    seed: UnifiedSeed,
    *,
    include_sensitive_name_routes: bool = False,
    limit: int = 20,
    timeout: int = 20,
) -> list[RegistryQuery]:
    country = seed.country
    out: list[RegistryQuery] = []

    if seed.kind is UnifiedSeedKind.ORGANIZATION:
        out.append(
            RegistryQuery(
                RegistryDomain.BUSINESS,
                RegistryQueryKind.NAME,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.COMPANY,
            )
        )
    elif seed.kind is UnifiedSeedKind.PERSON_NAME:
        # Business PERSON_NAME is useful for sole-trader registries and does not
        # imply a criminal/legal relationship. Court name search is opt-in.
        out.append(
            RegistryQuery(
                RegistryDomain.BUSINESS,
                RegistryQueryKind.PERSON_NAME,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.PERSON,
            )
        )
        if include_sensitive_name_routes:
            out.append(
                RegistryQuery(
                    RegistryDomain.COURT,
                    RegistryQueryKind.NAME,
                    seed.value,
                    country=country,
                    limit=limit,
                    timeout=timeout,
                    entity_kind=RegistryEntityKind.PERSON,
                )
            )
    elif seed.kind is UnifiedSeedKind.REGISTRATION_ID:
        out.append(
            RegistryQuery(
                RegistryDomain.BUSINESS,
                RegistryQueryKind.REGISTRATION_ID,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.COMPANY,
            )
        )
    elif seed.kind is UnifiedSeedKind.VAT_ID:
        out.append(
            RegistryQuery(
                RegistryDomain.BUSINESS,
                RegistryQueryKind.VAT_ID,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.COMPANY,
            )
        )
    elif seed.kind is UnifiedSeedKind.LEI:
        out.append(
            RegistryQuery(
                RegistryDomain.BUSINESS,
                RegistryQueryKind.LEI,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.COMPANY,
            )
        )
    elif seed.kind is UnifiedSeedKind.CASE_NUMBER:
        out.append(
            RegistryQuery(
                RegistryDomain.COURT,
                RegistryQueryKind.CASE_NUMBER,
                seed.value,
                country=country,
                limit=limit,
                timeout=timeout,
                entity_kind=RegistryEntityKind.COURT_CASE,
            )
        )

    return out


def build_search_plan(
    *,
    adapter_registry: Any,
    seeds: Iterable[UnifiedSeed],
    include_sensitive_name_routes: bool = False,
) -> UnifiedSearchPlan:
    plan = UnifiedSearchPlan(seeds=dedupe_seeds(seeds))
    for seed in plan.seeds:
        target = osint_target_for_seed(seed)
        if target is not None:
            plan.classic_seeds.append(seed)
            plan.open_web_seeds.append(seed)

        # Keywords are context by default, not independent broad-search roots.
        # They remain in plan.seeds so ranking can use them, but they do not fan
        # out into publication/archive APIs unless the analyst performs an
        # explicit keyword search in a specialized source page.
        if seed.kind is not UnifiedSeedKind.KEYWORD:
            automatic, guarded = plan_federation_routes(adapter_registry, seed)
            plan.federation_routes.extend((seed, route) for route in automatic)
            plan.guarded_routes.extend((seed, route) for route in guarded)

        for query in registry_queries_for_seed(
            seed,
            include_sensitive_name_routes=include_sensitive_name_routes,
        ):
            plan.registry_queries.append((seed, query))

    return plan


def extract_remote_pivots(
    record: Any,
    *,
    depth: int,
    parent_ref: str,
    default_country: str | None = None,
) -> list[UnifiedSeed]:
    """Extract only typed values from normalized identifiers/attributes.

    Source URLs are deliberately excluded: provenance links must not silently
    become recursion targets. Name/organization values may be exposed as review
    candidates, but only exact identifier classes are eligible for automatic
    recursion by :func:`is_exact_recursive_seed`.
    """
    values: list[tuple[str, Any]] = []
    identifiers = getattr(record, "identifiers", {}) or {}
    attributes = getattr(record, "attributes", {}) or {}
    metadata = getattr(record, "metadata", {}) or {}
    _collect_key_values(identifiers, values)
    _collect_key_values(attributes, values)
    _collect_key_values(metadata, values, max_depth=2)

    country = str(getattr(record, "country", "") or default_country or "").strip().upper() or None
    if country and (len(country) != 2 or not country.isalpha()):
        country = default_country

    out: list[UnifiedSeed] = []
    for key, raw in values:
        if any(marker in key.casefold() for marker in _SECRET_KEY_MARKERS):
            continue
        kind = _kind_from_field_name(key)
        if kind is None:
            continue
        for value in _scalar_values(raw):
            normalized = _validated_value(kind, value)
            if not normalized:
                continue
            candidate_only = kind in {
                UnifiedSeedKind.PERSON_NAME,
                UnifiedSeedKind.ORGANIZATION,
                UnifiedSeedKind.ADDRESS,
                UnifiedSeedKind.KEYWORD,
            }
            out.append(
                UnifiedSeed(
                    kind=kind,
                    value=normalized,
                    origin="discovered",
                    depth=depth,
                    country=country,
                    parent_ref=parent_ref,
                    candidate_only=candidate_only,
                    metadata={"field": key},
                )
            )
    return dedupe_seeds(out)


def _collect_key_values(value: Any, out: list[tuple[str, Any]], *, prefix: str = "", max_depth: int = 3) -> None:
    if max_depth < 0:
        return
    if isinstance(value, dict):
        for key, item in list(value.items())[:80]:
            name = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(item, dict):
                _collect_key_values(item, out, prefix=name, max_depth=max_depth - 1)
            elif isinstance(item, (list, tuple, set, frozenset)):
                out.append((name, item))
                for child in list(item)[:20]:
                    if isinstance(child, dict):
                        _collect_key_values(child, out, prefix=name, max_depth=max_depth - 1)
            else:
                out.append((name, item))


def _scalar_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item).strip() for item in list(value)[:30] if not isinstance(item, (dict, list, tuple, set, frozenset))]
    if value is None or isinstance(value, (dict, bytes, bytearray)):
        return []
    return [str(value).strip()]


def _kind_from_field_name(name: str) -> UnifiedSeedKind | None:
    key = str(name or "").casefold().replace("-", "_")
    # Order matters: email_domain is a domain, not an email address.
    if "email_domain" in key or "website_domain" in key or key.endswith("domain") or "hostname" in key:
        return UnifiedSeedKind.DOMAIN
    if "email" in key or key.endswith("mail"):
        return UnifiedSeedKind.EMAIL
    if "username" in key or "user_name" in key or key.endswith("login"):
        return UnifiedSeedKind.USERNAME
    if "phone" in key or "telephone" in key or "mobile" in key:
        return UnifiedSeedKind.PHONE
    if "orcid" in key:
        return UnifiedSeedKind.ORCID
    if re.search(r"(?:^|_)npi(?:_|$)", key):
        return UnifiedSeedKind.NPI
    if "cve" in key:
        return UnifiedSeedKind.CVE
    if "doi" in key:
        return UnifiedSeedKind.DOI
    if re.search(r"(?:^|_)lei(?:_|$)", key):
        return UnifiedSeedKind.LEI
    if "vat" in key:
        return UnifiedSeedKind.VAT_ID
    if "case_number" in key or "docket_number" in key:
        return UnifiedSeedKind.CASE_NUMBER
    if "asn" in key or "autonomous_system" in key:
        return UnifiedSeedKind.ASN
    if "sha256" in key or "sha1" in key or "md5" in key or "hash" in key:
        return UnifiedSeedKind.HASH
    if re.search(r"(?:^|_)ip(?:_|$)", key) or "ip_address" in key:
        return UnifiedSeedKind.IP
    if "repository" in key or key.endswith("repo"):
        return UnifiedSeedKind.REPOSITORY
    if "crypto" in key or "bitcoin" in key or "ethereum" in key or key.endswith("btc") or key.endswith("eth"):
        return UnifiedSeedKind.CRYPTO_ADDRESS
    if "registration" in key or "company_number" in key or "organization_number" in key or key.endswith("uei") or key.endswith("duns"):
        return UnifiedSeedKind.REGISTRATION_ID
    if "url" in key or "website" in key or "homepage" in key:
        return UnifiedSeedKind.URL
    if "organization" in key or "organisation" in key or "company" in key or "employer" in key or "recipient_name" in key:
        return UnifiedSeedKind.ORGANIZATION
    if "address" in key or "location" in key:
        return UnifiedSeedKind.ADDRESS
    if key.endswith("name") or "display_name" in key or "full_name" in key:
        return UnifiedSeedKind.PERSON_NAME
    return None


def _validated_value(kind: UnifiedSeedKind, value: str) -> str | None:
    raw = " ".join(str(value or "").strip().split())
    if not raw or len(raw) > 2048:
        return None
    if kind is UnifiedSeedKind.EMAIL:
        return raw.casefold() if _EMAIL_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.USERNAME:
        return raw.lstrip("@") if _USERNAME_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.PHONE:
        if not _PHONE_RE.fullmatch(raw):
            return None
        prefix = "+" if raw.startswith("+") else ""
        return prefix + "".join(ch for ch in raw if ch.isdigit())
    if kind is UnifiedSeedKind.DOMAIN:
        value = raw.casefold().rstrip(".")
        return value if _DOMAIN_RE.fullmatch(value) else None
    if kind is UnifiedSeedKind.URL:
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return None
        return raw if parsed.scheme.casefold() in {"http", "https"} and parsed.hostname else None
    if kind is UnifiedSeedKind.IP:
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return None
    if kind is UnifiedSeedKind.ASN:
        return raw.upper() if _ASN_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.HASH:
        return raw.lower() if _HASH_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.CVE:
        return raw.upper() if _CVE_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.ORCID:
        return raw.upper() if _ORCID_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.NPI:
        return raw if _NPI_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.LEI:
        return raw.upper() if _LEI_RE.fullmatch(raw) else None
    if kind is UnifiedSeedKind.DOI:
        return raw if _DOI_RE.fullmatch(raw) else None
    if kind in {UnifiedSeedKind.REGISTRATION_ID, UnifiedSeedKind.VAT_ID, UnifiedSeedKind.CASE_NUMBER, UnifiedSeedKind.CRYPTO_ADDRESS, UnifiedSeedKind.REPOSITORY}:
        return raw if len(raw) >= 2 else None
    if kind in {UnifiedSeedKind.PERSON_NAME, UnifiedSeedKind.ORGANIZATION, UnifiedSeedKind.ADDRESS, UnifiedSeedKind.KEYWORD}:
        return raw if len(raw) >= 2 else None
    return raw


def _normalize_value(kind: UnifiedSeedKind, value: str) -> str:
    validated = _validated_value(kind, value)
    if validated:
        return validated.casefold()
    return " ".join(str(value or "").strip().casefold().split())


def _country(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw:
        return None
    if len(raw) != 2 or not raw.isalpha():
        raise ValueError("Country must be a two-letter ISO code or blank.")
    return raw
