"""Strict full-name relevance for R13.20 unified investigation search.

The goal is not identity resolution.  It only answers a narrower question:
"does this upstream record actually appear to refer to the person name that was
searched?"  A positive answer keeps the record as a candidate; it never proves
that two people are the same person.

This layer deliberately runs *before* recursive pivots.  Name-search results
that only match one token (for example the same surname, or the same first
name) are retained in Raw UI output but cannot seed automatic follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable



_PERSON_LIKE_TYPES = {
    "person", "person_name", "individual", "natural_person", "researcher",
    "author", "author_profile", "professional", "sole_trader", "officer",
    "director", "founder", "inventor", "applicant", "contributor",
    "public_user", "user", "profile", "account", "social_profile",
}
_NAME_CONTAINER_KEYS = {
    "person", "individual", "author", "authors", "creator", "creators", "researcher", "contributor", "contributors",
    "officer", "director", "founder", "inventor", "applicant", "owner",
    "profile", "user", "account", "identity",
}
_QUERY_ECHO_MARKERS = {
    "query", "search", "input", "request", "target", "seed", "filter",
    "searched", "requested", "lookup",
}
# A deliberately conservative Cyrillic -> Latin fold.  Several letters have
# multiple common transliterations; the phonetic comparison below also folds
# Latin y -> i so Кириченко can match Kirichenko / Kyrychenko.
_CYRILLIC_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g",
    "д": "d", "е": "e", "ё": "e", "є": "e", "ж": "zh",
    "з": "z", "и": "i", "і": "i", "ї": "i", "й": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "shch", "ъ": "", "ы": "i", "ь": "", "э": "e",
    "ю": "iu", "я": "ia",
}


@dataclass(frozen=True, slots=True)
class PersonNameMatch:
    accepted: bool
    score: float
    reason: str
    query_tokens: tuple[str, ...]
    matched_tokens: tuple[str, ...] = ()
    matched_text: str = ""


def match_person_name_texts(query: str, texts: Iterable[Any]) -> PersonNameMatch:
    """Require the complete identifying parts of a multi-token person name.

    Two-part names require both tokens.  For three-or-more-part names the first
    and last token are mandatory and middle/patronymic matches increase the
    relevance score.  Token order is irrelevant.  No fuzzy edit-distance match
    is performed: a shared surname alone is intentionally insufficient.
    """
    query_tokens = tuple(_name_tokens(query))
    if not query_tokens:
        return PersonNameMatch(False, 0.0, "empty_name", ())

    candidates = [str(item or "").strip() for item in texts if str(item or "").strip()]
    if not candidates:
        return PersonNameMatch(False, 0.0, "no_candidate_name_text", query_tokens)

    if len(query_tokens) == 1:
        required_indexes = (0,)
    elif len(query_tokens) == 2:
        required_indexes = (0, 1)
    else:
        required_indexes = (0, len(query_tokens) - 1)

    query_forms = [_token_forms(token) for token in query_tokens]

    best: PersonNameMatch | None = None
    for candidate_text in candidates:
        candidate_tokens = _name_tokens(candidate_text)
        if not candidate_tokens:
            continue
        candidate_forms = [_token_forms(token) for token in candidate_tokens]

        matched_indexes: list[int] = []
        for index, forms in enumerate(query_forms):
            if any(forms & candidate for candidate in candidate_forms):
                matched_indexes.append(index)

        required_ok = all(index in matched_indexes for index in required_indexes)
        if not required_ok:
            current = PersonNameMatch(
                False,
                round(100.0 * len(matched_indexes) / max(1, len(query_tokens)), 1),
                "partial_name_only",
                query_tokens,
                tuple(query_tokens[index] for index in matched_indexes),
                candidate_text,
            )
        else:
            coverage = len(matched_indexes) / max(1, len(query_tokens))
            # Full two-token/full-name match = 100.  First+last match with a
            # missing patronymic remains strong but is not labelled exact.
            score = 100.0 if coverage >= 0.999 else 82.0 + min(14.0, coverage * 14.0)
            reason = "full_name_match" if coverage >= 0.999 else "first_last_match"
            current = PersonNameMatch(
                True,
                round(score, 1),
                reason,
                query_tokens,
                tuple(query_tokens[index] for index in matched_indexes),
                candidate_text,
            )

        if best is None or current.score > best.score:
            best = current
        if current.accepted and current.score >= 100.0:
            break

    return best or PersonNameMatch(False, 0.0, "no_name_tokens", query_tokens)


def match_person_name_record(query: str, record: Any) -> PersonNameMatch:
    """Evaluate only structured person-name fields from a normalized record.

    R13.21.2 deliberately ignores query/search echo fields and does not treat
    document/dataset titles as person names.  This prevents a publication that
    merely contains the searched name in request metadata from becoming an
    identity candidate.
    """
    texts: list[str] = []
    record_type = _record_type(record)
    display_name = str(getattr(record, "display_name", "") or "").strip()
    if display_name and _is_person_like_type(record_type):
        texts.append(display_name)

    for attr_name in ("attributes", "metadata"):
        value = getattr(record, attr_name, None)
        _collect_name_texts(value, texts)

    return match_person_name_texts(query, texts[:80])


def match_person_name_row(row: dict[str, Any]) -> PersonNameMatch:
    """Fallback relevance check for UI rows not preclassified by a source lane."""
    query = str(row.get("seed") or "").strip()
    texts = [row.get("title"), row.get("detail")]
    extra = row.get("identitySearchTexts")
    if isinstance(extra, (list, tuple)):
        texts.extend(extra[:30])
    return match_person_name_texts(query, texts)


def _collect_name_texts(
    value: Any,
    out: list[str],
    *,
    key: str = "",
    parent: str = "",
    depth: int = 0,
) -> None:
    if depth > 4 or len(out) >= 80 or value is None:
        return
    if isinstance(value, dict):
        combined = _combined_name_from_mapping(value)
        if combined:
            out.append(combined)
        for child_key, child in list(value.items())[:80]:
            name = _norm_key(child_key)
            if _is_query_echo_key(name):
                continue
            if isinstance(child, (dict, list, tuple, set, frozenset)):
                _collect_name_texts(
                    child, out, key=name, parent=key, depth=depth + 1
                )
            elif _name_scalar_allowed(name, key):
                text = str(child or "").strip()
                if text:
                    out.append(text)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for child in list(value)[:40]:
            _collect_name_texts(
                child, out, key=key, parent=parent, depth=depth + 1
            )
        return
    if _name_scalar_allowed(key, parent):
        text = str(value or "").strip()
        if text:
            out.append(text)


def _record_type(record: Any) -> str:
    raw = (
        getattr(record, "record_type", "")
        or getattr(getattr(record, "entity_kind", None), "value", "")
        or getattr(record, "entity_kind", "")
    )
    return _norm_key(raw)


def _is_person_like_type(value: Any) -> bool:
    normalized = _norm_key(value)
    if normalized in _PERSON_LIKE_TYPES:
        return True
    tokens = set(normalized.split("_"))
    return bool(tokens & {"person", "individual", "researcher", "author", "user", "profile", "account"})


def _is_query_echo_key(key: str) -> bool:
    normalized = _norm_key(key)
    return any(
        normalized == marker
        or normalized.startswith(marker + "_")
        or normalized.endswith("_" + marker)
        for marker in _QUERY_ECHO_MARKERS
    )


def _name_scalar_allowed(key: str, parent: str) -> bool:
    key = _norm_key(key)
    parent = _norm_key(parent)
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
    first = next(
        (normalized.get(k) for k in ("first_name", "given_name", "forename") if normalized.get(k)),
        None,
    )
    last = next(
        (normalized.get(k) for k in ("last_name", "family_name", "surname") if normalized.get(k)),
        None,
    )
    middle = next(
        (normalized.get(k) for k in ("middle_name", "patronymic") if normalized.get(k)),
        None,
    )
    if first and last:
        return " ".join(str(x).strip() for x in (first, middle, last) if str(x or "").strip())
    return ""


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")


def _name_tokens(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    # Unicode letters only; punctuation/hyphens are separators.  Single-letter
    # tokens are retained because some real records contain initials, but they
    # cannot satisfy a multi-character required token under exact forms.
    return [
        token
        for token in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
        if token
    ]


def _token_forms(token: str) -> set[str]:
    unicode_folded = _strip_marks(token.casefold())
    transliterated = "".join(_CYRILLIC_LATIN.get(ch, ch) for ch in unicode_folded)
    transliterated = re.sub(r"[^a-z]+", "", transliterated)
    forms = {unicode_folded}
    if transliterated:
        forms.add(transliterated)
        # Common East-Slavic transliteration variation: и may appear as i/y.
        # Folding y -> i is intentionally token-exact, not substring/fuzzy.
        forms.add(transliterated.replace("y", "i"))
    ascii_folded = re.sub(r"[^a-z]+", "", unicode_folded)
    if ascii_folded:
        forms.add(ascii_folded)
        forms.add(ascii_folded.replace("y", "i"))
    return {item for item in forms if item}


def _strip_marks(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )
