"""
Search index field extractor.

Converts structured SearchIndex representations into
typed searchable fields.

Architecture:

Domain object
    ↓
SearchIndexBuilder
    ↓
SearchIndex(title, content)
    ↓
SearchIndexFieldExtractor
    ↓
SearchIndexFields

The extractor is intentionally independent from:

- database sessions
- repositories
- retrieval algorithms
- ranking algorithms
- OSINT connectors
- UI

This allows the same field interpretation to be reused by:

- mathematical search ranking
- neural reranking
- entity resolution
- evidence scoring
- future OSINT pivoting

Important:

SearchIndex.content is not treated as one homogeneous
piece of text when it contains structured sections.

Example:

MESSAGE_TEXT:
hello

SENDER:
John

CHAT:
Example

becomes independent typed fields instead of three
independent matches against one flat string.
"""

from __future__ import annotations


from dataclasses import dataclass
from dataclasses import field
import re
from typing import Any


# ==========================================================
# Structured section syntax
# ==========================================================


_SECTION_PATTERN = re.compile(
    r"(?:\A|\n\n)"
    r"(?P<name>[A-Z][A-Z0-9_]{1,63})"
    r":\n",
    flags=re.MULTILINE,
)


# ==========================================================
# Extracted representation
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class SearchIndexFields:
    """
    Typed representation extracted from one SearchIndex.

    Unknown structured sections are preserved rather than
    discarded. This is important for future object types
    and OSINT enrichment fields.
    """

    object_type: str

    title: str

    raw_content: str

    sections: dict[
        str,
        tuple[str, ...],
    ] = field(
        default_factory=dict
    )

    # ======================================================
    # Generic access
    # ======================================================

    def values(
        self,
        name: str,
    ) -> tuple[str, ...]:
        """
        Return all values for one normalized field name.
        """

        normalized = (
            name.strip()
            .casefold()
        )

        if not normalized:

            return ()

        return self.sections.get(
            normalized,
            (),
        )

    def first(
        self,
        name: str,
    ) -> str:
        """
        Return first available value for one field.
        """

        values = self.values(
            name
        )

        if not values:

            return ""

        return values[0]

    def has(
        self,
        name: str,
    ) -> bool:
        """
        Whether field contains at least one value.
        """

        return bool(
            self.values(
                name
            )
        )

    # ======================================================
    # Common typed fields
    # ======================================================

    @property
    def message_text(
        self,
    ) -> str:

        return self.first(
            "message_text"
        )

    @property
    def sender(
        self,
    ) -> str:

        return self.first(
            "sender"
        )

    @property
    def receiver(
        self,
    ) -> str:

        return self.first(
            "receiver"
        )

    @property
    def chat(
        self,
    ) -> str:

        return self.first(
            "chat"
        )

    @property
    def external_id(
        self,
    ) -> str:

        return self.first(
            "external_id"
        )

    @property
    def sent_at(
        self,
    ) -> str:

        return self.first(
            "sent_at"
        )

    @property
    def metadata_text(
        self,
    ) -> str:

        return self.first(
            "metadata"
        )

    # ======================================================
    # Primary searchable representation
    # ======================================================

    @property
    def primary_text(
        self,
    ) -> str:
        """
        Return semantically primary text.

        For messages the message body is primary.

        For other object types the title is generally the
        strongest compact representation. If no title is
        available, raw content is used.
        """

        if (
            self.object_type
            == "message"
        ):

            return self.message_text

        if self.title:

            return self.title

        return self.raw_content

    # ======================================================
    # Context
    # ======================================================

    def context_fields(
        self,
    ) -> dict[str, str]:
        """
        Return common contextual fields.

        These fields describe an object but should not
        automatically be interpreted as its primary text.
        """

        values = {
            "sender": self.sender,
            "receiver": self.receiver,
            "chat": self.chat,
            "external_id": (
                self.external_id
            ),
            "sent_at": self.sent_at,
        }

        return {
            name: value
            for name, value
            in values.items()
            if value
        }


# ==========================================================
# Extractor
# ==========================================================


class SearchIndexFieldExtractor:
    """
    Extract typed fields from SearchIndex-like data.

    The extractor accepts either:

    - a SearchIndex object
    - another object exposing title/content/object_type
    - explicitly supplied object_type/title/content

    This keeps it usable outside SQLAlchemy and avoids
    database access inside ranking.
    """

    # ======================================================
    # Public API
    # ======================================================

    def extract(
        self,
        *,
        source: Any | None = None,
        object_type: Any | None = None,
        title: str = "",
        content: str = "",
    ) -> SearchIndexFields:
        """
        Extract normalized searchable fields.
        """

        resolved_object_type = (
            self._resolve_object_type(
                source=source,
                fallback=object_type,
            )
        )

        resolved_title = (
            self._resolve_text_attribute(
                source=source,
                name="title",
                fallback=title,
            )
        )

        resolved_content = (
            self._resolve_text_attribute(
                source=source,
                name="content",
                fallback=content,
            )
        )

        sections = (
            self._extract_sections(
                resolved_content
            )
        )

        return SearchIndexFields(
            object_type=(
                resolved_object_type
            ),
            title=(
                resolved_title
            ),
            raw_content=(
                resolved_content
            ),
            sections=sections,
        )

    # ======================================================
    # Structured section parsing
    # ======================================================

    def _extract_sections(
        self,
        content: str,
    ) -> dict[
        str,
        tuple[str, ...],
    ]:
        """
        Parse structured SearchIndex sections.

        Section markers are expected at the beginning of
        content or after a blank line:

            MESSAGE_TEXT:
            ...

            SENDER:
            ...

        Unknown uppercase section names are retained.
        """

        if not content:

            return {}

        matches = list(
            _SECTION_PATTERN.finditer(
                content
            )
        )

        if not matches:

            return {}

        collected: dict[
            str,
            list[str],
        ] = {}

        for index, match in enumerate(
            matches
        ):

            name = (
                match.group(
                    "name"
                )
                .strip()
                .casefold()
            )

            value_start = (
                match.end()
            )

            if (
                index + 1
                < len(matches)
            ):

                value_end = (
                    matches[
                        index + 1
                    ].start()
                )

            else:

                value_end = len(
                    content
                )

            value = (
                content[
                    value_start:value_end
                ]
                .strip()
            )

            if not value:

                continue

            collected.setdefault(
                name,
                [],
            ).append(
                value
            )

        return {
            name: tuple(
                values
            )
            for name, values
            in collected.items()
        }

    # ======================================================
    # Source resolution
    # ======================================================

    @staticmethod
    def _resolve_text_attribute(
        *,
        source: Any | None,
        name: str,
        fallback: str,
    ) -> str:
        """
        Resolve one string attribute without depending on a
        particular ORM model.
        """

        if source is not None:

            value = getattr(
                source,
                name,
                None,
            )

            if value is not None:

                normalized = str(
                    value
                ).strip()

                if normalized:

                    return normalized

        return (
            fallback
            or ""
        ).strip()

    @staticmethod
    def _resolve_object_type(
        *,
        source: Any | None,
        fallback: Any | None,
    ) -> str:
        """
        Normalize object type from enum or string.
        """

        value = fallback

        if source is not None:

            source_value = getattr(
                source,
                "object_type",
                None,
            )

            if source_value is not None:

                value = source_value

        if value is None:

            return ""

        enum_value = getattr(
            value,
            "value",
            None,
        )

        if enum_value is not None:

            value = enum_value

        return (
            str(
                value
            )
            .strip()
            .casefold()
        )