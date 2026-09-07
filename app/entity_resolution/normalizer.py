"""
Unified entity normalization.

Provides canonical representations
for investigation entities.

Responsibilities:

- normalize entity values by EntityType
- preserve stable comparison values
- normalize identifiers conservatively
- support entity resolution
- provide one shared normalization contract

Does NOT:

- compare entities
- calculate identity confidence
- merge entities
- access the database
- infer missing information
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata

from urllib.parse import (
    urlsplit,
    urlunsplit,
)

from app.models.entity import (
    EntityType,
)


class EntityNormalizer:
    """
    Unified normalizer for investigation entities.

    The normalizer is deterministic and conservative.

    It canonicalizes formatting but does not infer
    information that was not present in the source.
    """

    _LOCATION_COORDINATE_PATTERN = re.compile(
        r"""
        ^\s*
        (
            [+-]?
            (?:
                \d+(?:\.\d*)?
                |
                \.\d+
            )
        )
        \s*,\s*
        (
            [+-]?
            (?:
                \d+(?:\.\d*)?
                |
                \.\d+
            )
        )
        \s*$
        """,
        re.VERBOSE,
    )

    # ==========================================================
    # Public unified API
    # ==========================================================

    def normalize(
        self,
        entity_type: EntityType | str | None,
        value: str,
    ) -> str:
        """
        Normalize value according to entity type.

        Unknown or unsupported types fall back
        to conservative generic normalization.
        """

        resolved_type = self._resolve_entity_type(
            entity_type
        )

        if resolved_type == EntityType.EMAIL:

            return self.normalize_email(
                value
            )

        if resolved_type == EntityType.USERNAME:

            return self.normalize_username(
                value
            )

        if resolved_type == EntityType.PHONE:

            return self.normalize_phone(
                value
            )

        if resolved_type == EntityType.BANK_CARD:

            return self.normalize_bank_card(
                value
            )

        if resolved_type == EntityType.DOMAIN:

            return self.normalize_domain(
                value
            )

        if resolved_type == EntityType.URL:

            return self.normalize_url(
                value
            )

        if resolved_type == EntityType.IP:

            return self.normalize_ip(
                value
            )

        if resolved_type == EntityType.LOCATION:

            return self.normalize_location(
                value
            )

        if resolved_type == EntityType.ADDRESS:

            return self.normalize_address(
                value
            )

        if resolved_type == EntityType.ACCOUNT:

            return self.normalize_account(
                value
            )

        if resolved_type == EntityType.PERSON:

            return self.normalize_person(
                value
            )

        if resolved_type == EntityType.ORGANIZATION:

            return self.normalize_organization(
                value
            )

        return self.normalize_generic(
            value
        )

    # ==========================================================
    # Text entities
    # ==========================================================

    def normalize_person(
        self,
        value: str,
    ) -> str:
        """
        Normalize person name conservatively.

        No transliteration, token reordering,
        nickname inference or fuzzy processing
        happens at normalization stage.
        """

        return self.normalize_generic(
            value
        )

    def normalize_organization(
        self,
        value: str,
    ) -> str:
        """
        Normalize organization name conservatively.
        """

        return self.normalize_generic(
            value
        )

    def normalize_address(
        self,
        value: str,
    ) -> str:
        """
        Normalize address text conservatively.

        Address interpretation belongs to a later
        comparison/resolution layer.
        """

        return self.normalize_generic(
            value
        )

    def normalize_generic(
        self,
        value: str,
    ) -> str:
        """
        Normalize generic textual entity.

        Performs:

        - Unicode NFKC normalization
        - surrounding whitespace removal
        - internal whitespace collapsing
        - Unicode-aware case folding
        """

        normalized = self.normalize_text(
            value
        )

        return normalized.casefold()

    # ==========================================================
    # Email
    # ==========================================================

    def normalize_email(
        self,
        value: str,
    ) -> str:
        """
        Normalize email address.

        Does not apply provider-specific rules such as:

        - Gmail dot removal
        - plus-address stripping
        - domain-specific alias inference

        Such transformations could incorrectly merge
        distinct identities.
        """

        normalized = self.normalize_text(
            value
        )

        if normalized.lower().startswith(
            "mailto:"
        ):

            normalized = normalized[
                len("mailto:"):
            ].strip()

        return normalized.casefold()

    # ==========================================================
    # Username
    # ==========================================================

    def normalize_username(
        self,
        value: str,
    ) -> str:
        """
        Normalize username.

        Leading @ characters are display syntax
        and are not part of username identity.
        """

        normalized = self.normalize_text(
            value
        ).casefold()

        while normalized.startswith("@"):

            normalized = normalized[1:]

        return normalized.strip()

    # ==========================================================
    # Phone
    # ==========================================================

    def normalize_phone(
        self,
        value: str,
    ) -> str:
        """
        Normalize phone number formatting.

        Only digits are retained.

        Country code is NOT inferred.
        Prefixes are NOT converted automatically.

        Example:

            +380 (67) 123-45-67
            ->
            380671234567
        """

        text = unicodedata.normalize(
            "NFKC",
            str(
                value
                or ""
            ),
        )

        return "".join(
            character
            for character in text
            if character.isdigit()
        )

    def normalize_bank_card(
        self,
        value: str,
    ) -> str:
        """
        Normalize a bank card number.

        Only decimal digits are retained.

        No issuer inference, BIN lookup or formatting
        transformation is performed here.
        """

        text = unicodedata.normalize(
            "NFKC",
            str(
                value
                or ""
            ),
        )

        return "".join(
            character
            for character in text
            if character.isdigit()
        )

    # ==========================================================
    # Domain
    # ==========================================================

    def normalize_domain(
        self,
        value: str,
    ) -> str:
        """
        Normalize domain / hostname.

        Removes:

        - URL scheme
        - path
        - query
        - fragment
        - trailing dot

        Subdomains are preserved.

        Example:

            HTTPS://Example.COM/path
            ->
            example.com
        """

        normalized = self.normalize_text(
            value
        ).casefold()

        if not normalized:

            return ""

        candidate = normalized

        if "://" not in candidate:

            candidate = (
                "//"
                + candidate
            )

        try:

            parsed = urlsplit(
                candidate
            )

            hostname = (
                parsed.hostname
                or ""
            ).strip()

            if hostname:

                return hostname.rstrip(".")

        except (
            TypeError,
            ValueError,
        ):

            pass

        normalized = re.sub(
            r"^[a-z][a-z0-9+\-.]*://",
            "",
            normalized,
            flags=re.IGNORECASE,
        )

        normalized = normalized.split(
            "/",
            1,
        )[0]

        normalized = normalized.split(
            "?",
            1,
        )[0]

        normalized = normalized.split(
            "#",
            1,
        )[0]

        return normalized.rstrip(
            "./"
        )

    # ==========================================================
    # URL
    # ==========================================================

    def normalize_url(
        self,
        value: str,
    ) -> str:
        """
        Normalize URL conservatively.

        Normalizes scheme and hostname case,
        removes URL fragment and redundant
        trailing slash.

        Query parameters are preserved because
        they may contain investigation-relevant
        identifiers.
        """

        normalized = self.normalize_text(
            value
        )

        if not normalized:

            return ""

        candidate = normalized

        added_scheme = False

        if "://" not in candidate:

            candidate = (
                "https://"
                + candidate
            )

            added_scheme = True

        try:

            parsed = urlsplit(
                candidate
            )

            scheme = (
                parsed.scheme
                or "https"
            ).casefold()

            hostname = (
                parsed.hostname
                or ""
            ).casefold()

            if not hostname:

                return normalized.casefold()

            port = parsed.port

            if (
                port is not None
                and not (
                    (
                        scheme == "http"
                        and port == 80
                    )
                    or
                    (
                        scheme == "https"
                        and port == 443
                    )
                )
            ):

                netloc = (
                    f"{hostname}:{port}"
                )

            else:

                netloc = hostname

            path = (
                parsed.path
                or ""
            )

            if path == "/":

                path = ""

            elif path:

                path = path.rstrip("/")

            result = urlunsplit(
                (
                    scheme,
                    netloc,
                    path,
                    parsed.query,
                    "",
                )
            )

            if added_scheme:

                # Keep a deterministic URL representation.
                # We intentionally retain https:// so the
                # output is unambiguous.
                return result

            return result

        except (
            TypeError,
            ValueError,
        ):

            return normalized.casefold()

    # ==========================================================
    # IP
    # ==========================================================

    def normalize_ip(
        self,
        value: str,
    ) -> str:
        """
        Normalize IPv4 or IPv6 using Python's
        canonical ipaddress representation.
        """

        normalized = self.normalize_text(
            value
        )

        if not normalized:

            return ""

        try:

            return str(
                ipaddress.ip_address(
                    normalized
                )
            )

        except ValueError:

            return normalized.casefold()

    # ==========================================================
    # Location
    # ==========================================================

    def normalize_location(
        self,
        value: str,
    ) -> str:
        """
        Normalize LOCATION entity.

        Coordinate values preserve the existing
        ImageGpsLocationService identity format:

            display:
                45.6768222, 28.6131556

            normalized:
                45.6768222,28.6131556

        Named locations use conservative textual
        normalization.
        """

        normalized = self.normalize_text(
            value
        )

        if not normalized:

            return ""

        match = (
            self._LOCATION_COORDINATE_PATTERN
            .match(
                normalized
            )
        )

        if match is not None:

            latitude = match.group(
                1
            )

            longitude = match.group(
                2
            )

            return (
                f"{latitude},"
                f"{longitude}"
            )

        return normalized.casefold()

    # ==========================================================
    # Account identifiers
    # ==========================================================

    def normalize_account(
        self,
        value: str,
    ) -> str:
        """
        Normalize generic account identifier.

        Platform-specific account rules belong
        to later metadata-aware resolution.
        """

        return self.normalize_generic(
            value
        )

    # ==========================================================
    # Shared helpers
    # ==========================================================

    def normalize_text(
        self,
        value: str,
    ) -> str:
        """
        Normalize Unicode and whitespace
        without changing semantic case.
        """

        normalized = unicodedata.normalize(
            "NFKC",
            str(
                value
                or ""
            ),
        )

        return " ".join(
            normalized
            .strip()
            .split()
        )

    @staticmethod
    def _resolve_entity_type(
        entity_type: EntityType | str | None,
    ) -> EntityType | None:
        """
        Resolve enum or string entity type.

        Unknown types deliberately return None
        and use generic normalization.
        """

        if isinstance(
            entity_type,
            EntityType,
        ):

            return entity_type

        if entity_type is None:

            return None

        try:

            return EntityType(
                str(
                    entity_type
                )
                .strip()
                .lower()
            )

        except (
            TypeError,
            ValueError,
        ):

            return None