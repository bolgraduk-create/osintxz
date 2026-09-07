from __future__ import annotations

import re
from dataclasses import (
    asdict,
    dataclass,
)
from typing import (
    Any,
    Mapping,
)
from urllib.parse import (
    parse_qs,
    unquote_plus,
    urlencode,
    urlparse,
)


_SITE_RE = re.compile(
    r"(?<!\w)site:([a-z0-9.-]+\.[a-z]{2,})(?!\w)",
    re.IGNORECASE,
)

_QUOTED_RE = re.compile(
    r'"([^"]+)"'
)


@dataclass(
    frozen=True,
    slots=True,
)
class NormalizedLead:
    """
    Normalized discovery/search lead.

    A lead is a search direction and must not be treated
    as a confirmed finding.
    """

    category: str
    source: str
    value: str

    platform_domain: str | None

    original_url: str | None
    original_query: str | None

    canonical_query: str

    query_variants: tuple[
        str,
        ...
    ]

    # Backward-compatible canonical search URLs.
    search_urls: dict[
        str,
        str,
    ]

    # Lead Engine v1.1:
    # one set of search-engine URLs for every query variant.
    variant_searches: tuple[
        dict[str, Any],
        ...
    ]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert lead to a serializable dictionary.
        """

        return asdict(
            self
        )


class LeadNormalizer:
    """
    Convert raw connector leads into structured search leads.

    The normalizer does not send requests to search engines.
    It only prepares URLs for explicit user navigation.
    """

    @classmethod
    def normalize(
        cls,
        item: Mapping[
            str,
            Any,
        ],
    ) -> NormalizedLead:
        """
        Normalize one serialized OSINT lead.
        """

        metadata = item.get(
            "metadata"
        )

        if not isinstance(
            metadata,
            Mapping,
        ):
            metadata = {}

        category = str(
            metadata.get(
                "category"
            )
            or item.get(
                "category"
            )
            or "Search"
        ).strip()

        source = str(
            item.get(
                "source"
            )
            or "Search lead"
        ).strip()

        value = str(
            item.get(
                "value"
            )
            or ""
        ).strip()

        original_url = cls._clean_url(
            item.get(
                "url"
            )
        )

        original_query = cls._extract_query(
            original_url
        )

        platform_domain = (
            cls._extract_site_domain(
                original_query
            )
        )

        quoted_terms = (
            cls._extract_quoted_terms(
                original_query
            )
        )

        if (
            not quoted_terms
            and value
        ):
            quoted_terms = [
                value
            ]

        query_variants = (
            cls._build_query_variants(
                platform_domain=(
                    platform_domain
                ),
                terms=quoted_terms,
                fallback_query=(
                    original_query
                ),
                fallback_value=value,
            )
        )

        canonical_query = (
            query_variants[-1]
            if query_variants
            else cls._fallback_query(
                platform_domain=(
                    platform_domain
                ),
                value=value,
            )
        )

        search_urls = (
            cls._build_search_urls(
                canonical_query
            )
        )

        variant_searches = (
            cls._build_variant_searches(
                query_variants
            )
        )

        return NormalizedLead(
            category=category,
            source=source,
            value=value,
            platform_domain=(
                platform_domain
            ),
            original_url=(
                original_url
            ),
            original_query=(
                original_query
            ),
            canonical_query=(
                canonical_query
            ),
            query_variants=tuple(
                query_variants
            ),
            search_urls=(
                search_urls
            ),
            variant_searches=(
                variant_searches
            ),
        )

    @staticmethod
    def is_lead(
        item: Mapping[
            str,
            Any,
        ],
    ) -> bool:
        """
        Detect whether a serialized item is a discovery lead.
        """

        if (
            str(
                item.get(
                    "kind"
                )
                or ""
            )
            .strip()
            .casefold()
            == "lead"
        ):
            return True

        if bool(
            item.get(
                "lead_only",
                False,
            )
        ):
            return True

        metadata = item.get(
            "metadata"
        )

        return bool(
            isinstance(
                metadata,
                Mapping,
            )
            and metadata.get(
                "lead_only",
                False,
            )
        )

    @staticmethod
    def _clean_url(
        value: Any,
    ) -> str | None:
        """
        Accept only HTTP/HTTPS URLs.
        """

        text = str(
            value
            or ""
        ).strip()

        if not text:
            return None

        try:
            parsed = urlparse(
                text
            )
        except Exception:
            return None

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return None

        if not parsed.netloc:
            return None

        return text

    @staticmethod
    def _extract_query(
        url: str | None,
    ) -> str | None:
        """
        Extract q= from a search URL.
        """

        if not url:
            return None

        try:

            parsed = urlparse(
                url
            )

            values = parse_qs(
                parsed.query
            )

            query = (
                values.get(
                    "q",
                    [None],
                )[0]
            )

            if query is None:
                return None

            return (
                unquote_plus(
                    str(
                        query
                    )
                )
                .strip()
                or None
            )

        except Exception:
            return None

    @staticmethod
    def _extract_site_domain(
        query: str | None,
    ) -> str | None:
        """
        Extract site:example.com from a query.
        """

        if not query:
            return None

        match = _SITE_RE.search(
            query
        )

        if not match:
            return None

        domain = (
            match.group(1)
            .strip()
            .lower()
            .rstrip(".")
        )

        if domain.startswith(
            "www."
        ):
            domain = domain[
                4:
            ]

        return (
            domain
            or None
        )

    @staticmethod
    def _extract_quoted_terms(
        query: str | None,
    ) -> list[str]:
        """
        Extract unique quoted values from the raw query.
        """

        if not query:
            return []

        result: list[str] = []
        seen: set[str] = set()

        for match in (
            _QUOTED_RE.finditer(
                query
            )
        ):

            term = (
                match.group(1)
                .strip()
            )

            key = (
                term.casefold()
            )

            if (
                not term
                or key in seen
            ):
                continue

            seen.add(
                key
            )

            result.append(
                term
            )

        return result

    @classmethod
    def _build_query_variants(
        cls,
        *,
        platform_domain: str | None,
        terms: list[str],
        fallback_query: str | None,
        fallback_value: str,
    ) -> list[str]:
        """
        Build independent exact queries plus one combined query.
        """

        clean_terms: list[str] = []
        seen: set[str] = set()

        for term in terms:

            normalized = str(
                term
            ).strip()

            key = (
                normalized.casefold()
            )

            if (
                not normalized
                or key in seen
            ):
                continue

            seen.add(
                key
            )

            clean_terms.append(
                normalized
            )

        variants: list[str] = []

        # Individual exact-match queries.
        for term in clean_terms:

            quoted = (
                cls._quote_term(
                    term
                )
            )

            if platform_domain:

                variants.append(
                    (
                        f"site:"
                        f"{platform_domain} "
                        f"{quoted}"
                    )
                )

            else:

                variants.append(
                    quoted
                )

        # Combined OR query.
        if len(
            clean_terms
        ) > 1:

            joined = (
                " OR ".join(
                    cls._quote_term(
                        term
                    )
                    for term
                    in clean_terms
                )
            )

            if platform_domain:

                variants.append(
                    (
                        f"site:"
                        f"{platform_domain} "
                        f"({joined})"
                    )
                )

            else:

                variants.append(
                    f"({joined})"
                )

        if not variants:

            fallback = (
                fallback_query
                or fallback_value
            ).strip()

            if fallback:

                variants.append(
                    fallback
                )

        return variants

    @classmethod
    def _build_variant_searches(
        cls,
        queries: list[str],
    ) -> tuple[
        dict[str, Any],
        ...
    ]:
        """
        Build Google/Bing/DuckDuckGo URLs for every query.

        The last multi-term OR query is labeled "combined".
        Earlier entries are exact variants.
        """

        result: list[
            dict[str, Any]
        ] = []

        for index, query in enumerate(
            queries,
            start=1,
        ):

            is_combined = (
                " OR " in query
            )

            result.append(
                {
                    "index": index,
                    "kind": (
                        "combined"
                        if is_combined
                        else "exact"
                    ),
                    "label": (
                        "Combined"
                        if is_combined
                        else f"Exact {index}"
                    ),
                    "query": query,
                    "search_urls": (
                        cls._build_search_urls(
                            query
                        )
                    ),
                }
            )

        return tuple(
            result
        )

    @staticmethod
    def _quote_term(
        term: str,
    ) -> str:
        """
        Quote one exact search term.
        """

        escaped = (
            term.replace(
                '"',
                r'\"',
            )
        )

        return (
            f'"{escaped}"'
        )

    @classmethod
    def _fallback_query(
        cls,
        *,
        platform_domain: str | None,
        value: str,
    ) -> str:
        """
        Generate a basic query when the raw lead has none.
        """

        if not value:

            if platform_domain:

                return (
                    f"site:"
                    f"{platform_domain}"
                )

            return ""

        quoted = cls._quote_term(
            value
        )

        if platform_domain:

            return (
                f"site:"
                f"{platform_domain} "
                f"{quoted}"
            )

        return quoted

    @staticmethod
    def _build_search_urls(
        query: str,
    ) -> dict[str, str]:
        """
        Generate manual browser search links.
        """

        if not query:
            return {}

        encoded = urlencode(
            {
                "q": query,
            }
        )

        return {
            "google": (
                "https://www.google.com/search?"
                + encoded
            ),
            "bing": (
                "https://www.bing.com/search?"
                + encoded
            ),
            "duckduckgo": (
                "https://duckduckgo.com/?"
                + encoded
            ),
        }
