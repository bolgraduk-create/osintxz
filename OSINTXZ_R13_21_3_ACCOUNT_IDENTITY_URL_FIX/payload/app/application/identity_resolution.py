"""R13.21 — explainable multi-signal identity relevance.

This module does *not* assert that two records are the same person.  It scores
how well a normalized candidate aligns with analyst-supplied known data and
explains both supporting and conflicting signals.  A name-only match is never
sufficient for an automatic identity pivot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any, Iterable

from app.application.person_name_relevance import match_person_name_texts


_SECRET_MARKERS = (
    "password", "passwd", "secret", "token", "cookie", "session",
    "authorization", "private_key", "privatekey", "credential",
)


_PERSON_LIKE_TYPES = {
    "person", "person_name", "individual", "natural_person", "researcher",
    "author", "author_profile", "professional", "sole_trader", "officer",
    "director", "founder", "inventor", "applicant", "contributor",
}
_ACCOUNT_LIKE_TYPES = {
    "account", "public_account", "public_user", "user", "profile",
    "social_profile", "username", "online_account", "online_identity",
}
_NON_PERSON_CONTENT_TYPES = {
    "document", "dataset", "publication", "research_output", "article", "book",
    "archive_item", "archive_record", "regulatory_document", "cve", "company",
    "organization", "legal_entity", "court_case", "court_decision",
}
_NAME_CONTAINER_KEYS = {
    "person", "individual", "author", "authors", "creator", "creators", "researcher", "contributor", "contributors",
    "officer", "director", "founder", "inventor", "applicant", "profile",
    "user", "account", "identity",
}
_QUERY_ECHO_MARKERS = {
    "query", "search", "input", "request", "target", "seed", "filter",
    "searched", "requested", "lookup",
}


@dataclass(frozen=True, slots=True)
class KnownIdentityProfile:
    names: tuple[str, ...] = ()
    birth_dates: frozenset[str] = frozenset()
    emails: frozenset[str] = frozenset()
    phones: frozenset[str] = frozenset()
    usernames: frozenset[str] = frozenset()
    countries: frozenset[str] = frozenset()
    regions: frozenset[str] = frozenset()
    cities: frozenset[str] = frozenset()
    postal_codes: frozenset[str] = frozenset()
    addresses: frozenset[str] = frozenset()
    organizations: frozenset[str] = frozenset()
    orcids: frozenset[str] = frozenset()
    npis: frozenset[str] = frozenset()

    @property
    def signal_categories(self) -> int:
        return sum(
            bool(value)
            for value in (
                self.names, self.birth_dates, self.emails, self.phones,
                self.usernames, self.countries, self.regions, self.cities,
                self.postal_codes, self.addresses, self.organizations,
                self.orcids, self.npis,
            )
        )


@dataclass(slots=True)
class IdentitySignals:
    names: set[str] = field(default_factory=set)
    birth_dates: set[str] = field(default_factory=set)
    emails: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    usernames: set[str] = field(default_factory=set)
    countries: set[str] = field(default_factory=set)
    regions: set[str] = field(default_factory=set)
    cities: set[str] = field(default_factory=set)
    postal_codes: set[str] = field(default_factory=set)
    addresses: set[str] = field(default_factory=set)
    organizations: set[str] = field(default_factory=set)
    orcids: set[str] = field(default_factory=set)
    npis: set[str] = field(default_factory=set)

    def merge(self, other: "IdentitySignals") -> None:
        for name in self.__dataclass_fields__:
            getattr(self, name).update(getattr(other, name))

    def to_payload(self) -> dict[str, list[str]]:
        return {
            name: sorted(getattr(self, name), key=str.casefold)
            for name in self.__dataclass_fields__
            if getattr(self, name)
        }

    @classmethod
    def from_payload(cls, payload: Any) -> "IdentitySignals":
        out = cls()
        if not isinstance(payload, dict):
            return out
        for name in cls.__dataclass_fields__:
            values = payload.get(name)
            if isinstance(values, (list, tuple, set, frozenset)):
                getattr(out, name).update(
                    str(item).strip() for item in values if str(item).strip()
                )
        return out


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    status: str
    score: float
    matched: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    matched_categories: tuple[str, ...] = ()
    conflict_categories: tuple[str, ...] = ()
    pivot_allowed: bool = False

    @property
    def label(self) -> str:
        return {
            "strong": "Strong alignment",
            "supported": "Supported candidate",
            "possible": "Possible candidate",
            "conflicting": "Conflicting data",
            "insufficient": "Insufficient evidence",
            "not_applicable": "Not identity-scored",
        }.get(self.status, self.status.replace("_", " ").title())

    @property
    def summary(self) -> str:
        parts = list(self.matched[:4])
        if self.conflicts:
            parts.append("Conflicts: " + "; ".join(self.conflicts[:3]))
        if not parts:
            return "No independent identity signals were available."
        return " · ".join(parts)

    def row_fields(self) -> dict[str, Any]:
        return {
            "identityStatus": self.status,
            "identityLabel": self.label,
            "identityAlignmentScore": self.score,
            "identityMatchedSignals": list(self.matched),
            "identityConflictSignals": list(self.conflicts),
            "identityMatchedCategories": list(self.matched_categories),
            "identityConflictCategories": list(self.conflict_categories),
            "identityPivotAllowed": self.pivot_allowed,
            "identitySummary": self.summary,
        }


def build_known_identity_profile(profile: dict[str, Any] | None) -> KnownIdentityProfile:
    data = dict(profile or {})
    first = _text(data.get("firstName"))
    middle = _text(data.get("middleName"))
    last = _text(data.get("lastName"))
    primary = " ".join(item for item in (first, middle, last) if item).strip()
    names = []
    if primary:
        names.append(primary)
    names.extend(_split_values(data.get("aliases")))

    return KnownIdentityProfile(
        names=tuple(dict.fromkeys(item for item in names if item)),
        birth_dates=frozenset(filter(None, (_normalize_date(v) for v in _split_values(data.get("birthDate"))))),
        emails=frozenset(_normalize_email(v) for v in _split_values(data.get("emails")) if _normalize_email(v)),
        phones=frozenset(_normalize_phone(v) for v in _split_values(data.get("phones")) if _normalize_phone(v)),
        usernames=frozenset(_normalize_username(v) for v in _split_values(data.get("usernames")) if _normalize_username(v)),
        countries=frozenset(_norm_text(v) for v in _split_values(data.get("country")) if _norm_text(v)),
        regions=frozenset(_norm_text(v) for v in _split_values(data.get("region")) if _norm_text(v)),
        cities=frozenset(_norm_text(v) for v in _split_values(data.get("city")) if _norm_text(v)),
        postal_codes=frozenset(_norm_compact(v) for v in _split_values(data.get("postalCode")) if _norm_compact(v)),
        addresses=frozenset(_norm_text(v) for v in _split_values(data.get("address")) if _norm_text(v)),
        organizations=frozenset(_norm_text(v) for v in _split_values(data.get("organizations")) if _norm_text(v)),
        orcids=frozenset(_norm_compact(v) for v in _split_values(data.get("orcids")) if _norm_compact(v)),
        npis=frozenset(_norm_compact(v) for v in _split_values(data.get("npis")) if _norm_compact(v)),
    )


def extract_identity_signals(value: Any) -> IdentitySignals:
    """Extract bounded identity hints without trusting query-echo metadata.

    Names are accepted only from person-like records or explicit structured
    person containers (author/creator/person/profile).  Generic document,
    dataset and publication titles never become identity names.
    """
    signals = IdentitySignals()
    if isinstance(value, dict):
        title = _text(value.get("title") or value.get("display_name") or value.get("displayName"))
        type_name = _norm_key(value.get("type") or value.get("record_type") or value.get("entityKind"))
        if title and is_identity_candidate_type(type_name):
            signals.names.add(title)
        identifiers = value.get("identifiers")
        if isinstance(identifiers, dict):
            _collect_mapping(identifiers, signals, depth=0, key="identifiers")
        for key in ("attributes", "metadata", "identityContext", "_identityContext"):
            _collect_mapping(value.get(key), signals, depth=0, key=_norm_key(key))
        return signals

    display = _text(getattr(value, "display_name", ""))
    record_type_obj = getattr(value, "record_type", "") or getattr(value, "entity_kind", "")
    record_type = _norm_key(getattr(record_type_obj, "value", None) or record_type_obj)
    if display and is_identity_candidate_type(record_type):
        signals.names.add(display)
    identifiers = getattr(value, "identifiers", None)
    if isinstance(identifiers, dict):
        _collect_mapping(identifiers, signals, depth=0, key="identifiers")
    for attr in ("attributes", "metadata"):
        _collect_mapping(getattr(value, attr, None), signals, depth=0, key=attr)
    return signals


def is_account_candidate_type(value: Any) -> bool:
    """Return True for online-account records that are signals, not people."""
    normalized = _norm_key(value)
    if not normalized:
        return False
    if normalized in _ACCOUNT_LIKE_TYPES:
        return True
    tokens = set(normalized.split("_"))
    return bool(tokens & {"account", "username", "profile"}) and not bool(
        tokens & {"person", "individual", "researcher", "author"}
    )


def is_account_candidate_record(value: Any) -> bool:
    if isinstance(value, dict):
        record_type = value.get("type") or value.get("record_type") or value.get("entityKind")
    else:
        record_type_obj = getattr(value, "record_type", "") or getattr(value, "entity_kind", "")
        record_type = getattr(record_type_obj, "value", None) or record_type_obj
    return is_account_candidate_type(record_type)


def is_identity_candidate_type(value: Any) -> bool:
    normalized = _norm_key(value)
    if not normalized or normalized in _NON_PERSON_CONTENT_TYPES:
        return False
    # Accounts/usernames can corroborate a person, but they are not a second
    # PERSON candidate and must never create a false identity conflict.
    if is_account_candidate_type(normalized):
        return False
    if normalized in _PERSON_LIKE_TYPES:
        return True
    tokens = set(normalized.split("_"))
    return bool(tokens & {"person", "individual", "researcher", "author"})


def is_identity_candidate_record(value: Any) -> bool:
    if isinstance(value, dict):
        record_type = value.get("type") or value.get("record_type") or value.get("entityKind")
    else:
        record_type_obj = getattr(value, "record_type", "") or getattr(value, "entity_kind", "")
        record_type = getattr(record_type_obj, "value", None) or record_type_obj
    return is_identity_candidate_type(record_type)


def resolve_identity(
    profile: KnownIdentityProfile,
    signals: IdentitySignals,
    *,
    person_query: str | None = None,
) -> IdentityResolution:
    if profile.signal_categories == 0:
        return IdentityResolution("not_applicable", 0.0)

    matched: list[str] = []
    conflicts: list[str] = []
    matched_categories: list[str] = []
    conflict_categories: list[str] = []
    positive = 0.0
    negative = 0.0
    anchors = 0
    hard_conflict = False

    query_names = list(profile.names)
    if person_query and person_query.strip() and person_query.strip() not in query_names:
        query_names.insert(0, person_query.strip())
    if query_names and signals.names:
        best = None
        for query in query_names:
            current = match_person_name_texts(query, signals.names)
            if best is None or current.score > best.score:
                best = current
        if best and best.accepted:
            positive += 22.0
            matched.append(f"Full name matches ({best.matched_text})")
            matched_categories.append("name")
        elif best:
            negative -= 28.0
            conflicts.append("Name does not match the known full name")
            conflict_categories.append("name")

    def exact(category: str, known: frozenset[str], found: set[str], weight: float, *, conflict_weight: float = 0.0, anchor: bool = False, hard: bool = False, label: str | None = None) -> None:
        nonlocal positive, negative, anchors, hard_conflict
        if not known or not found:
            return
        overlap = set(known) & set(found)
        pretty = label or category.replace("_", " ").title()
        if overlap:
            positive += weight
            matched.append(f"{pretty} matches")
            matched_categories.append(category)
            if anchor:
                anchors += 1
        elif conflict_weight:
            negative -= conflict_weight
            conflicts.append(f"{pretty} conflicts")
            conflict_categories.append(category)
            if hard:
                hard_conflict = True

    exact("birth_date", profile.birth_dates, signals.birth_dates, 32.0, conflict_weight=55.0, anchor=True, hard=True, label="Birth date")
    exact("email", profile.emails, signals.emails, 38.0, conflict_weight=18.0, anchor=True, label="Email")
    exact("phone", profile.phones, signals.phones, 34.0, conflict_weight=18.0, anchor=True, label="Phone")
    exact("username", profile.usernames, signals.usernames, 18.0, conflict_weight=8.0, label="Username")
    exact("orcid", profile.orcids, signals.orcids, 45.0, conflict_weight=70.0, anchor=True, hard=True, label="ORCID")
    exact("npi", profile.npis, signals.npis, 42.0, conflict_weight=65.0, anchor=True, hard=True, label="NPI")
    exact("country", profile.countries, signals.countries, 5.0, label="Country")
    exact("region", profile.regions, signals.regions, 6.0, label="Region")
    exact("city", profile.cities, signals.cities, 9.0, label="City")
    exact("postal_code", profile.postal_codes, signals.postal_codes, 8.0, label="Postal code")
    exact("address", profile.addresses, signals.addresses, 22.0, label="Address")
    exact("organization", profile.organizations, signals.organizations, 12.0, label="Organization")

    score = round(max(0.0, min(100.0, positive + negative)), 1)
    positive_categories = len(set(matched_categories))

    if hard_conflict or (negative <= -28.0 and positive < 38.0):
        status = "conflicting"
    elif positive >= 60.0 and positive_categories >= 2:
        status = "strong"
    elif anchors >= 2 and positive_categories >= 2:
        status = "strong"
    elif positive >= 40.0 and positive_categories >= 2:
        status = "supported"
    elif anchors >= 1 and positive >= 30.0:
        status = "supported"
    elif positive >= 25.0 and positive_categories >= 2:
        status = "possible"
    elif positive > 0:
        status = "insufficient"
    elif conflicts:
        status = "conflicting"
    else:
        status = "not_applicable"

    pivot_allowed = status in {"strong", "supported"} and not conflicts
    return IdentityResolution(
        status=status,
        score=score,
        matched=tuple(dict.fromkeys(matched)),
        conflicts=tuple(dict.fromkeys(conflicts)),
        matched_categories=tuple(dict.fromkeys(matched_categories)),
        conflict_categories=tuple(dict.fromkeys(conflict_categories)),
        pivot_allowed=pivot_allowed,
    )


def resolve_identity_record(
    profile: KnownIdentityProfile,
    record: Any,
    *,
    person_query: str | None = None,
) -> tuple[IdentityResolution, IdentitySignals]:
    signals = extract_identity_signals(record)
    return resolve_identity(profile, signals, person_query=person_query), signals


def resolve_identity_row(
    profile: KnownIdentityProfile,
    row: dict[str, Any],
    *,
    merged_signals: IdentitySignals | None = None,
) -> tuple[IdentityResolution, IdentitySignals]:
    signals = merged_signals or extract_identity_signals(row)
    person_query = str(row.get("seed") or "") if _norm_key(row.get("seedType")) == "person_name" else None
    return resolve_identity(profile, signals, person_query=person_query), signals


def _collect_mapping(
    value: Any,
    signals: IdentitySignals,
    *,
    depth: int,
    key: str = "",
    parent: str = "",
) -> None:
    if value is None or depth > 4:
        return
    if isinstance(value, dict):
        combined = _combined_name_from_mapping(value)
        if combined and not _is_query_echo_key(key):
            signals.names.add(combined)
        for index, (child_key, child) in enumerate(value.items()):
            if index >= 100:
                break
            name = _norm_key(child_key)
            if any(marker in name for marker in _SECRET_MARKERS) or _is_query_echo_key(name):
                continue
            _collect_mapping(
                child, signals, depth=depth + 1, key=name, parent=key
            )
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for child in list(value)[:80]:
            _collect_mapping(
                child, signals, depth=depth + 1, key=key, parent=parent
            )
        return

    text = _text(value)
    if not text:
        return
    key = _norm_key(key)
    parent = _norm_key(parent)
    if _name_scalar_allowed(key, parent):
        signals.names.add(text)
    elif _has(key, "birth", "dob", "date_of_birth", "birth_date", "birthdate"):
        normalized = _normalize_date(text)
        if normalized:
            signals.birth_dates.add(normalized)
    elif _has(key, "email", "e_mail"):
        normalized = _normalize_email(text)
        if normalized:
            signals.emails.add(normalized)
    elif _has(key, "phone", "telephone", "mobile"):
        normalized = _normalize_phone(text)
        if normalized:
            signals.phones.add(normalized)
    elif _has(key, "username", "user_name", "handle", "login"):
        normalized = _normalize_username(text)
        if normalized:
            signals.usernames.add(normalized)
    elif _has(key, "orcid"):
        signals.orcids.add(_norm_compact(text))
    elif _has(key, "npi", "npi_number"):
        signals.npis.add(_norm_compact(text))
    elif _has(key, "country", "country_code", "country_name", "nation"):
        signals.countries.add(_norm_text(text))
    elif _has(key, "city", "locality", "town"):
        signals.cities.add(_norm_text(text))
    elif _has(key, "region", "state", "province"):
        signals.regions.add(_norm_text(text))
    elif _has(key, "postal", "postcode", "zip"):
        signals.postal_codes.add(_norm_compact(text))
    elif _has(key, "address", "street"):
        signals.addresses.add(_norm_text(text))
    elif _has(key, "organization", "organisation", "company", "employer", "affiliation", "institution", "workplace"):
        signals.organizations.add(_norm_text(text))


def _is_query_echo_key(key: str) -> bool:
    normalized = _norm_key(key)
    return any(
        normalized == marker
        or normalized.startswith(marker + "_")
        or normalized.endswith("_" + marker)
        for marker in _QUERY_ECHO_MARKERS
    )


def _name_scalar_allowed(key: str, parent: str) -> bool:
    if not key or _is_query_echo_key(key) or _is_query_echo_key(parent):
        return False
    direct = {
        "full_name", "fullname", "person_name", "author", "creator",
        "researcher", "contributor", "officer", "director", "founder",
        "inventor", "applicant",
    }
    if key in direct:
        return True
    if key in {"name", "display_name"} and parent in _NAME_CONTAINER_KEYS:
        return True
    return False


def _combined_name_from_mapping(value: dict[str, Any]) -> str:
    normalized = {_norm_key(k): v for k, v in value.items()}
    first = next((normalized.get(k) for k in ("first_name", "given_name", "forename") if normalized.get(k)), None)
    last = next((normalized.get(k) for k in ("last_name", "family_name", "surname") if normalized.get(k)), None)
    middle = next((normalized.get(k) for k in ("middle_name", "patronymic") if normalized.get(k)), None)
    if first and last:
        return " ".join(str(x).strip() for x in (first, middle, last) if str(x or "").strip())
    return ""


def _is_name_key(key: str) -> bool:
    return _name_scalar_allowed(_norm_key(key), "")


def _has(key: str, *markers: str) -> bool:
    return any(key == marker or key.endswith("_" + marker) or marker in key for marker in markers)


def _split_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        out: list[str] = []
        for item in value:
            out.extend(_split_values(item))
        return out
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[\r\n;,]+", text) if item.strip()]


def _normalize_date(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


def _normalize_email(value: Any) -> str:
    text = _text(value).casefold()
    return text if "@" in text and " " not in text else ""


def _normalize_phone(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    prefix = "+" if text.startswith("+") else ""
    digits = "".join(ch for ch in text if ch.isdigit())
    return prefix + digits if len(digits) >= 6 else ""


def _normalize_username(value: Any) -> str:
    return _text(value).lstrip("@").casefold()


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value).casefold()).strip(" .,:;|-_")


def _norm_compact(value: Any) -> str:
    return re.sub(r"[\s-]+", "", _text(value)).upper()


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).casefold()).strip("_")


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())
