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


_NAME_KEY_MARKERS = (
    "name", "author", "creator", "person", "owner", "officer",
    "director", "founder", "applicant", "inventor", "contributor",
)

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
    """Evaluate a normalized Federation/Registry record against a person seed."""
    texts: list[str] = []
    display_name = str(getattr(record, "display_name", "") or "").strip()
    if display_name:
        texts.append(display_name)

    for attr_name in ("attributes", "metadata"):
        value = getattr(record, attr_name, None)
        _collect_name_texts(value, texts)

    # RegistryRecord commonly stores person-relevant information directly in
    # metadata, while RemoteSourceRecord uses attributes.  Keep both bounded.
    return match_person_name_texts(query, texts[:80])


def match_person_name_row(row: dict[str, Any]) -> PersonNameMatch:
    """Fallback relevance check for UI rows not preclassified by a source lane."""
    query = str(row.get("seed") or "").strip()
    texts = [row.get("title"), row.get("detail")]
    extra = row.get("identitySearchTexts")
    if isinstance(extra, (list, tuple)):
        texts.extend(extra[:30])
    return match_person_name_texts(query, texts)


def _collect_name_texts(value: Any, out: list[str], *, key: str = "", depth: int = 0) -> None:
    if depth > 4 or len(out) >= 80 or value is None:
        return
    if isinstance(value, dict):
        for child_key, child in list(value.items())[:80]:
            name = str(child_key or "").casefold().replace("-", "_")
            if isinstance(child, (dict, list, tuple, set, frozenset)):
                _collect_name_texts(child, out, key=name, depth=depth + 1)
            elif any(marker in name for marker in _NAME_KEY_MARKERS):
                text = str(child or "").strip()
                if text:
                    out.append(text)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for child in list(value)[:40]:
            _collect_name_texts(child, out, key=key, depth=depth + 1)
        return
    if any(marker in key for marker in _NAME_KEY_MARKERS):
        text = str(value or "").strip()
        if text:
            out.append(text)


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
