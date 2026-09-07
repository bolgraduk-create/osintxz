"""
Investigation query expansion service.

Produces conservative deterministic variants of one
investigation search query.

Architecture:

InvestigationSearchQuery
        ↓
QueryExpansionService
        ↓
QueryExpansionVariant[]
        ↓
UnifiedSearchService
        ↓
retrievers

The service is intentionally conservative.

It does NOT:

- execute search
- access the database
- use embeddings
- call an LLM
- invent semantic synonyms
- perform entity resolution
- perform OSINT enrichment

Initial expansion strategies:

- original query preservation
- whitespace normalization
- outer quote removal
- username normalization
- email components
- URL host extraction
- phone normalization
- short proper-name word-order reversal
- conservative Cyrillic → Latin transliteration

Every expanded variant carries:

- kind
- weight
- explanation
- metadata

This allows expanded matches to receive lower influence
than the original query during later result aggregation.
"""

from __future__ import annotations


from dataclasses import dataclass
from dataclasses import field
from enum import Enum
import re
from typing import Any
from urllib.parse import urlparse


from app.investigation.search_query import (
    InvestigationSearchQuery,
)


# ==========================================================
# Patterns
# ==========================================================


_EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    flags=re.UNICODE,
)


_USERNAME_PATTERN = re.compile(
    r"^@[A-Za-z0-9_.-]{2,}$"
)


_PHONE_PATTERN = re.compile(
    r"^\+?[\d\s().-]{6,}$"
)


_CYRILLIC_PATTERN = re.compile(
    r"[А-Яа-яЁё]"
)


_NAME_TOKEN_PATTERN = re.compile(
    r"^[^\W\d_]+(?:[-'][^\W\d_]+)*$",
    flags=re.UNICODE,
)


# ==========================================================
# Transliteration table
# ==========================================================


_CYRILLIC_TRANSLITERATION = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


# ==========================================================
# Expansion kind
# ==========================================================


class QueryExpansionKind(str, Enum):
    """
    Deterministic query expansion categories.
    """

    ORIGINAL = "original"

    NORMALIZED = "normalized"

    DEQUOTED = "dequoted"

    USERNAME = "username"

    EMAIL_LOCAL = "email_local"

    EMAIL_DOMAIN = "email_domain"

    URL_HOST = "url_host"

    PHONE = "phone"

    NAME_ORDER = "name_order"

    TRANSLITERATION = "transliteration"


# ==========================================================
# Expansion result
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class QueryExpansionVariant:
    """
    One query variant.

    weight describes relative retrieval importance.

    It is NOT:

    - evidence confidence
    - identity confidence
    - final search score
    """

    text: str

    kind: QueryExpansionKind

    weight: float

    reason: str

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ==========================================================
# Configuration
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class QueryExpansionConfig:
    """
    Conservative query expansion configuration.
    """

    max_variants: int = 8

    normalized_weight: float = 0.99

    dequoted_weight: float = 0.98

    username_weight: float = 0.95

    email_local_weight: float = 0.88

    email_domain_weight: float = 0.85

    url_host_weight: float = 0.90

    phone_weight: float = 0.95

    name_order_weight: float = 0.90

    transliteration_weight: float = 0.88

    enable_transliteration: bool = True

    enable_name_order: bool = True

    def __post_init__(
        self,
    ) -> None:

        if self.max_variants < 1:

            raise ValueError(
                "max_variants must be at least 1."
            )

        weights = (
            self.normalized_weight,
            self.dequoted_weight,
            self.username_weight,
            self.email_local_weight,
            self.email_domain_weight,
            self.url_host_weight,
            self.phone_weight,
            self.name_order_weight,
            self.transliteration_weight,
        )

        for weight in weights:

            if not (
                0.0
                <= weight
                <= 1.0
            ):

                raise ValueError(
                    "Query expansion weights must "
                    "be between 0.0 and 1.0."
                )


# ==========================================================
# Service
# ==========================================================


class QueryExpansionService:
    """
    Produce safe deterministic query variants.
    """

    def __init__(
        self,
        config: (
            QueryExpansionConfig
            | None
        ) = None,
    ) -> None:

        self.config = (
            config
            or QueryExpansionConfig()
        )

    # ======================================================
    # Public API
    # ======================================================

    def expand(
        self,
        query: InvestigationSearchQuery,
    ) -> list[
        QueryExpansionVariant
    ]:
        """
        Expand one InvestigationSearchQuery.

        The original query is always first.

        If query expansion is disabled, only the original
        query is returned.
        """

        text = query.query.strip()

        if not text:

            return []

        variants: list[
            QueryExpansionVariant
        ] = []

        seen: set[str] = set()

        self._add_variant(
            variants=variants,
            seen=seen,
            text=text,
            kind=(
                QueryExpansionKind.ORIGINAL
            ),
            weight=1.0,
            reason=(
                "Original investigation query."
            ),
        )

        if not query.enable_query_expansion:

            return variants

        # ----------------------------------------------
        # Whitespace normalization
        # ----------------------------------------------

        normalized = (
            self._normalize_whitespace(
                text
            )
        )

        self._add_variant(
            variants=variants,
            seen=seen,
            text=normalized,
            kind=(
                QueryExpansionKind.NORMALIZED
            ),
            weight=(
                self.config
                .normalized_weight
            ),
            reason=(
                "Whitespace-normalized query."
            ),
        )

        # ----------------------------------------------
        # Outer quotes
        # ----------------------------------------------

        dequoted = (
            self._remove_outer_quotes(
                normalized
            )
        )

        if (
            dequoted
            != normalized
        ):

            self._add_variant(
                variants=variants,
                seen=seen,
                text=dequoted,
                kind=(
                    QueryExpansionKind
                    .DEQUOTED
                ),
                weight=(
                    self.config
                    .dequoted_weight
                ),
                reason=(
                    "Removed outer query quotes."
                ),
            )

        working_text = (
            dequoted
            or normalized
        )

        # ----------------------------------------------
        # Username
        # ----------------------------------------------

        if _USERNAME_PATTERN.fullmatch(
            working_text
        ):

            self._add_variant(
                variants=variants,
                seen=seen,
                text=(
                    working_text[1:]
                ),
                kind=(
                    QueryExpansionKind.USERNAME
                ),
                weight=(
                    self.config
                    .username_weight
                ),
                reason=(
                    "Username without @ prefix."
                ),
                metadata={
                    "source": working_text,
                },
            )

        # ----------------------------------------------
        # Email
        # ----------------------------------------------

        if _EMAIL_PATTERN.fullmatch(
            working_text
        ):

            local_part, domain = (
                working_text.rsplit(
                    "@",
                    1,
                )
            )

            self._add_variant(
                variants=variants,
                seen=seen,
                text=local_part,
                kind=(
                    QueryExpansionKind
                    .EMAIL_LOCAL
                ),
                weight=(
                    self.config
                    .email_local_weight
                ),
                reason=(
                    "Email local-part expansion."
                ),
                metadata={
                    "email": working_text,
                },
            )

            self._add_variant(
                variants=variants,
                seen=seen,
                text=domain,
                kind=(
                    QueryExpansionKind
                    .EMAIL_DOMAIN
                ),
                weight=(
                    self.config
                    .email_domain_weight
                ),
                reason=(
                    "Email domain expansion."
                ),
                metadata={
                    "email": working_text,
                },
            )

        # ----------------------------------------------
        # URL
        # ----------------------------------------------

        host = (
            self._extract_url_host(
                working_text
            )
        )

        if host:

            self._add_variant(
                variants=variants,
                seen=seen,
                text=host,
                kind=(
                    QueryExpansionKind
                    .URL_HOST
                ),
                weight=(
                    self.config
                    .url_host_weight
                ),
                reason=(
                    "URL hostname expansion."
                ),
                metadata={
                    "url": working_text,
                },
            )

            if host.startswith(
                "www."
            ):

                self._add_variant(
                    variants=variants,
                    seen=seen,
                    text=host[4:],
                    kind=(
                        QueryExpansionKind
                        .URL_HOST
                    ),
                    weight=(
                        self.config
                        .url_host_weight
                    ),
                    reason=(
                        "URL hostname without "
                        "www prefix."
                    ),
                    metadata={
                        "url": working_text,
                    },
                )

        # ----------------------------------------------
        # Phone
        # ----------------------------------------------

        if _PHONE_PATTERN.fullmatch(
            working_text
        ):

            digits = "".join(
                character
                for character
                in working_text
                if character.isdigit()
            )

            if len(digits) >= 6:

                normalized_phone = (
                    "+"
                    + digits
                    if working_text.startswith(
                        "+"
                    )
                    else digits
                )

                self._add_variant(
                    variants=variants,
                    seen=seen,
                    text=normalized_phone,
                    kind=(
                        QueryExpansionKind.PHONE
                    ),
                    weight=(
                        self.config
                        .phone_weight
                    ),
                    reason=(
                        "Normalized phone-number "
                        "representation."
                    ),
                )

        # ----------------------------------------------
        # Proper-name order
        # ----------------------------------------------

        if (
            self.config.enable_name_order
            and self._looks_like_proper_name(
                working_text
            )
        ):

            tokens = (
                working_text.split()
            )

            reversed_name = " ".join(
                reversed(
                    tokens
                )
            )

            self._add_variant(
                variants=variants,
                seen=seen,
                text=reversed_name,
                kind=(
                    QueryExpansionKind
                    .NAME_ORDER
                ),
                weight=(
                    self.config
                    .name_order_weight
                ),
                reason=(
                    "Alternative proper-name "
                    "word order."
                ),
            )

        # ----------------------------------------------
        # Cyrillic transliteration
        # ----------------------------------------------

        if (
            self.config.enable_transliteration
            and self._should_transliterate(
                working_text
            )
        ):

            transliterated = (
                self._transliterate_cyrillic(
                    working_text
                )
            )

            self._add_variant(
                variants=variants,
                seen=seen,
                text=transliterated,
                kind=(
                    QueryExpansionKind
                    .TRANSLITERATION
                ),
                weight=(
                    self.config
                    .transliteration_weight
                ),
                reason=(
                    "Conservative Cyrillic-to-Latin "
                    "transliteration."
                ),
            )

        return variants[
            :self.config.max_variants
        ]

    # ======================================================
    # Variant collection
    # ======================================================

    def _add_variant(
        self,
        *,
        variants: list[
            QueryExpansionVariant
        ],
        seen: set[str],
        text: str,
        kind: QueryExpansionKind,
        weight: float,
        reason: str,
        metadata: (
            dict[str, Any]
            | None
        ) = None,
    ) -> None:
        """
        Add unique deterministic variant.

        Deduplication is case-insensitive and whitespace
        normalized.
        """

        text = (
            self._normalize_whitespace(
                text
            )
        )

        if not text:

            return

        key = text.casefold()

        if key in seen:

            return

        if (
            len(variants)
            >= self.config.max_variants
        ):

            return

        seen.add(
            key
        )

        variants.append(
            QueryExpansionVariant(
                text=text,
                kind=kind,
                weight=weight,
                reason=reason,
                metadata=(
                    dict(
                        metadata
                    )
                    if metadata
                    else {}
                ),
            )
        )

    # ======================================================
    # Name detection
    # ======================================================

    @staticmethod
    def _looks_like_proper_name(
        text: str,
    ) -> bool:
        """
        Conservative proper-name heuristic.

        Only 2-3 alphabetic title-cased tokens qualify.

        This deliberately avoids reversing normal search
        phrases such as:

            планы на субботу
        """

        tokens = text.split()

        if not (
            2
            <= len(tokens)
            <= 3
        ):

            return False

        for token in tokens:

            if not _NAME_TOKEN_PATTERN.fullmatch(
                token
            ):

                return False

            first_alpha = next(
                (
                    character
                    for character
                    in token
                    if character.isalpha()
                ),
                "",
            )

            if (
                not first_alpha
                or not first_alpha.isupper()
            ):

                return False

        return True

    # ======================================================
    # Transliteration
    # ======================================================

    @staticmethod
    def _should_transliterate(
        text: str,
    ) -> bool:
        """
        Transliterate only short identifier/name-like
        queries.

        Rules:

        - one Cyrillic token may be an identifier,
          username or name;

        - multi-token input is transliterated only when it
          looks like a proper name;

        - ordinary natural-language phrases are excluded.

        Examples:

            Алена
                -> Alena

            Учиха Алена
                -> Uchikha Alena

            планы на субботу
                -> no transliteration
        """

        if not _CYRILLIC_PATTERN.search(
            text
        ):

            return False

        if len(text) > 80:

            return False

        tokens = text.split()

        if not tokens:

            return False

        if len(tokens) == 1:

            return True

        if len(tokens) > 3:

            return False

        return (
            QueryExpansionService
            ._looks_like_proper_name(
                text
            )
        )

    @staticmethod
    def _transliterate_cyrillic(
        text: str,
    ) -> str:
        """
        Basic deterministic Cyrillic → Latin mapping.

        This is search expansion, not a legal-name
        transliteration standard.
        """

        result: list[str] = []

        for character in text:

            lower = (
                character.casefold()
            )

            mapped = (
                _CYRILLIC_TRANSLITERATION
                .get(
                    lower
                )
            )

            if mapped is None:

                result.append(
                    character
                )

                continue

            if character.isupper():

                if mapped:

                    mapped = (
                        mapped[0].upper()
                        + mapped[1:]
                    )

            result.append(
                mapped
            )

        return "".join(
            result
        )

    # ======================================================
    # URL
    # ======================================================

    @staticmethod
    def _extract_url_host(
        text: str,
    ) -> str:
        """
        Extract hostname from explicit URL-like input.
        """

        lowered = text.casefold()

        looks_like_url = (
            lowered.startswith(
                "http://"
            )
            or lowered.startswith(
                "https://"
            )
            or lowered.startswith(
                "www."
            )
        )

        if not looks_like_url:

            return ""

        candidate = text

        if lowered.startswith(
            "www."
        ):

            candidate = (
                "https://"
                + text
            )

        try:

            parsed = urlparse(
                candidate
            )

        except ValueError:

            return ""

        return (
            parsed.hostname
            or ""
        ).strip()

    # ======================================================
    # Text normalization
    # ======================================================

    @staticmethod
    def _normalize_whitespace(
        text: str,
    ) -> str:

        return " ".join(
            text.split()
        )

    @staticmethod
    def _remove_outer_quotes(
        text: str,
    ) -> str:
        """
        Remove one matching pair of outer quotation marks.
        """

        if len(text) < 2:

            return text

        quote_pairs = {
            ('"', '"'),
            ("'", "'"),
            ("«", "»"),
            ("“", "”"),
        }

        if (
            text[0],
            text[-1],
        ) not in quote_pairs:

            return text

        return text[
            1:-1
        ].strip()