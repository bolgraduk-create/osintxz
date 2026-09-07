"""
Entity analyzer.

Extracts, validates, normalizes and deduplicates
investigation identifiers from unstructured text.

Pipeline:

    Raw text
        ↓
    Candidate extraction
        ↓
    Context filtering
        ↓
    Validation
        ↓
    Normalization
        ↓
    Deduplication
        ↓
    Result
"""

from __future__ import annotations

import ipaddress
import re

from collections import Counter
from typing import Any

from app.entity_resolution.normalizer import EntityNormalizer
from app.models.entity import EntityType


class EntityAnalyzer:
    """
    Conservative investigation entity extractor.

    Important rule:

    extraction and validation are separate stages.

    A sequence merely looking like an identifier is not
    automatically accepted as an entity.
    """

    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}\b"
    )

    URL_PATTERN = re.compile(
        r"https?://[^\s<>\"']+",
        re.IGNORECASE,
    )

    DOMAIN_PATTERN = re.compile(
        r"\b(?:[A-Za-z0-9-]+\.)+"
        r"[A-Za-z]{2,}\b"
    )

    # Candidate only. Validation happens afterwards.
    PHONE_PATTERN = re.compile(
        r"(?<![\w])"
        r"\+?"
        r"(?:"
        r"\(\d{1,4}\)"
        r"|"
        r"\d{1,4}"
        r")"
        r"(?:[\s().-]*\d){6,14}"
        r"(?![\w])"
    )

    BANK_CARD_PATTERN = re.compile(
        r"(?<!\w)"
        r"(?:\d[\s-]?){12,18}\d"
        r"(?!\w)"
    )

    # Context is used only to disambiguate short Luhn-valid values
    # (13--15 digits), which overlap the E.164 phone-number range.
    # It does not infer issuer, ownership or account validity.
    BANK_CARD_CONTEXT_PATTERN = re.compile(
        r"(?<!\w)(?:"
        r"bank\s*card"
        r"|payment\s*card"
        r"|card(?:\s*(?:number|no\.?|#))?"
        r"|visa"
        r"|master\s*card"
        r"|mastercard"
        r"|amex"
        r"|american\s+express"
        r"|банковск\w*\s+карт\w*"
        r"|номер\s+карт\w*"
        r"|карт(?:а|ы|е|у|ой|очка|очки|ке|ку)"
        r"|банківськ\w*\s+карт\w*"
        r"|номер\s+карт\w*"
        r"|платіжн\w*\s+карт\w*"
        r"|карт(?:ка|ки|ці|ку|кою)"
        r")(?!\w)",
        re.IGNORECASE,
    )

    USERNAME_PATTERN = re.compile(
        r"(?<![A-Za-z0-9_])"
        r"@[A-Za-z0-9_]{3,32}"
        r"\b"
    )

    IPV4_PATTERN = re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    )

    HASH_PATTERN = re.compile(
        r"\b(?:"
        r"[A-Fa-f0-9]{32}"
        r"|"
        r"[A-Fa-f0-9]{40}"
        r"|"
        r"[A-Fa-f0-9]{64}"
        r")\b"
    )

    DATE_LIKE_PATTERN = re.compile(
        r"""
        (?<!\d)
        (?:
            # --------------------------------------------------
            # DD.MM / DD.MM.YYYY
            # DD/MM / DD/MM/YYYY
            # DD-MM / DD-MM-YYYY
            # --------------------------------------------------

            (?:
                0?[1-9]
                |
                [12]\d
                |
                3[01]
            )
            (?P<date_sep>[./-])
            (?:
                0?[1-9]
                |
                1[0-2]
            )
            (?:
                (?P=date_sep)
                \d{2,4}
            )?

            |

            # --------------------------------------------------
            # YYYY-MM-DD
            # --------------------------------------------------

            \d{4}
            -
            (?:
                0?[1-9]
                |
                1[0-2]
            )
            -
            (?:
                0?[1-9]
                |
                [12]\d
                |
                3[01]
            )

            |

            # --------------------------------------------------
            # HH:MM
            # --------------------------------------------------

            (?:
                [01]?\d
                |
                2[0-3]
            )
            :
            [0-5]\d
        )
        (?!\d)
        """,
        re.VERBOSE,
    )

    def __init__(
        self,
        *,
        normalizer: EntityNormalizer | None = None,
    ) -> None:

        self.normalizer = (
            normalizer
            or EntityNormalizer()
        )

    # ==========================================================
    # Main API
    # ==========================================================

    def analyze(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        if not text:

            return []

        entities: list[dict[str, Any]] = []

        entities.extend(
            self.extract_emails(text)
        )

        entities.extend(
            self.extract_urls(text)
        )

        entities.extend(
            self.extract_domains(text)
        )

        entities.extend(
            self.extract_bank_cards(text)
        )

        entities.extend(
            self.extract_phone_numbers(text)
        )

        entities.extend(
            self.extract_usernames(text)
        )

        entities.extend(
            self.extract_ipv4(text)
        )

        entities.extend(
            self.extract_hashes(text)
        )

        return self.merge_duplicates(
            entities
        )

    # ==========================================================
    # Email
    # ==========================================================

    def extract_emails(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []

        for value in self.EMAIL_PATTERN.findall(
            text
        ):

            results.append(
                self.create_entity(
                    EntityType.EMAIL,
                    value,
                    confidence=1.0,
                )
            )

        return results

    # ==========================================================
    # URL
    # ==========================================================

    def extract_urls(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []

        for value in self.URL_PATTERN.findall(
            text
        ):

            cleaned = value.rstrip(
                ".,;:!?)]}"
            )

            results.append(
                self.create_entity(
                    EntityType.URL,
                    cleaned,
                    confidence=1.0,
                )
            )

        return results

    # ==========================================================
    # Domain
    # ==========================================================

    def extract_domains(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []

        for value in self.DOMAIN_PATTERN.findall(
            text
        ):

            if self._domain_is_email_component(
                text,
                value,
            ):

                continue

            results.append(
                self.create_entity(
                    EntityType.DOMAIN,
                    value,
                    confidence=0.9,
                )
            )

        return results

    # ==========================================================
    # Phone
    # ==========================================================

    def extract_phone_numbers(
        self,
        text: str,
    ) -> list[dict[str, Any]]:
        """
        Extract conservative phone-number candidates.

        The detector intentionally does not infer a country code or
        rewrite national numbers into an international form.  Its job
        is to preserve identifiers exactly as they appeared in the
        evidence while storing a deterministic digit-only comparison
        value through :class:`EntityNormalizer`.

        False-positive protection is applied before a PHONE entity is
        emitted:

        - URLs are protected;
        - valid IP addresses are protected;
        - date/time spans are protected;
        - Luhn-valid payment-card candidates are protected;
        - degenerate repeated-digit sequences are rejected;
        - ambiguous unformatted 13--15 digit identifiers are rejected.
        """

        results: list[dict[str, Any]] = []

        # ----------------------------------------------------------
        # Protected ranges
        # ----------------------------------------------------------

        url_ranges = [
            match.span()
            for match
            in self.URL_PATTERN.finditer(text)
        ]

        date_ranges = [
            match.span()
            for match
            in self.DATE_LIKE_PATTERN.finditer(text)
        ]

        ip_ranges: list[tuple[int, int]] = []

        for match in self.IPV4_PATTERN.finditer(text):
            if self.validate_ip(match.group(0)):
                ip_ranges.append(match.span())

        bank_card_ranges: list[tuple[int, int]] = []

        for match in self.BANK_CARD_PATTERN.finditer(text):
            value = match.group(0).strip()
            normalized_card = (
                self.normalizer.normalize_bank_card(value)
            )

            if self._is_bank_card_candidate(
                text=text,
                value=value,
                normalized=normalized_card,
                span=match.span(),
            ):
                bank_card_ranges.append(match.span())

        protected_ranges = (
            url_ranges
            + ip_ranges
            + date_ranges
            + bank_card_ranges
        )

        # ----------------------------------------------------------
        # Phone candidates
        # ----------------------------------------------------------

        for match in self.PHONE_PATTERN.finditer(text):
            value = match.group(0).strip()

            if self._range_overlaps(
                match.span(),
                protected_ranges,
            ):
                continue

            normalized = self.normalizer.normalize_phone(value)

            if self.looks_like_date_or_time(value):
                continue

            if not self.validate_phone(
                value=value,
                normalized=normalized,
            ):
                continue

            # A payment-card identifier must never be duplicated as
            # PHONE.  Short Luhn-valid values (13--15 digits) are only
            # treated as cards when nearby payment-card context makes
            # that interpretation unambiguous.
            if self._is_bank_card_candidate(
                text=text,
                value=value,
                normalized=normalized,
                span=match.span(),
            ):
                continue

            has_explicit_plus = value.startswith("+")
            has_phone_formatting = any(
                character in value
                for character in (
                    " ",
                    "-",
                    "(",
                    ")",
                )
            )

            confidence = 0.9

            if has_explicit_plus:
                confidence = 0.95
            elif not has_phone_formatting:
                confidence = 0.85

            results.append(
                self.create_entity(
                    EntityType.PHONE,
                    value,
                    confidence=confidence,
                    metadata={
                        "identifier_kind": "phone",
                        "validation": "conservative",
                        "digit_count": len(normalized),
                        "explicit_international_prefix": (
                            has_explicit_plus
                        ),
                    },
                )
            )

        return results

    def looks_like_date_or_time(
        self,
        value: str,
    ) -> bool:
        """Return True when the whole candidate is date/time text."""

        text = value.strip()

        date_matches = list(
            self.DATE_LIKE_PATTERN.finditer(text)
        )

        if not date_matches:
            return False

        leftover = text

        for match in reversed(date_matches):
            leftover = (
                leftover[:match.start()]
                + leftover[match.end():]
            )

        leftover = re.sub(
            r"[\s\-–—,;]+",
            "",
            leftover,
        )

        return leftover == ""

    def validate_phone(
        self,
        *,
        value: str,
        normalized: str,
    ) -> bool:
        """
        Validate a phone candidate without country inference.

        Region-specific validity belongs to a later optional adapter
        (for example libphonenumber when investigation context provides
        a reliable region).  Core extraction stays deterministic and
        source-agnostic.
        """

        if not normalized or not normalized.isdigit():
            return False

        digit_count = len(normalized)

        # E.164 allows at most 15 digits.  Seven digits is retained as
        # the conservative minimum for local telephone numbers.
        if not 7 <= digit_count <= 15:
            return False

        # Obviously meaningless identifiers such as 0000000000 or
        # 1111111111 should not become PHONE entities.
        if len(set(normalized)) == 1:
            return False

        compact = value.strip()

        has_phone_formatting = (
            compact.startswith("+")
            or any(
                character in compact
                for character in (
                    " ",
                    "-",
                    "(",
                    ")",
                )
            )
        )

        # Long opaque digit-only strings are more likely to be database
        # IDs, transaction identifiers or other reference numbers.
        if digit_count >= 13 and not has_phone_formatting:
            return False

        return True

    # ==========================================================
    # Username
    # ==========================================================

    def extract_usernames(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []

        url_ranges = [
            match.span()
            for match
            in self.URL_PATTERN.finditer(text)
        ]

        for match in self.USERNAME_PATTERN.finditer(
            text
        ):

            if self._range_overlaps(
                match.span(),
                url_ranges,
            ):

                continue

            results.append(
                self.create_entity(
                    EntityType.USERNAME,
                    match.group(0),
                    confidence=0.8,
                )
            )

        return results

    # ==========================================================
    # IP
    # ==========================================================

    def extract_ipv4(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []

        for value in self.IPV4_PATTERN.findall(
            text
        ):

            if not self.validate_ip(value):

                continue

            results.append(
                self.create_entity(
                    EntityType.IP,
                    value,
                    confidence=0.95,
                )
            )

        return results

    def extract_bank_cards(
        self,
        text: str,
    ) -> list[dict[str, Any]]:
        """
        Extract conservative payment-card-number candidates.

        A candidate must pass the Luhn checksum.  Values of 16--19
        digits are outside the E.164 phone range and may be accepted
        without contextual hints.  Luhn-valid 13--15 digit values are
        ambiguous with phone numbers and therefore require nearby
        payment-card context before they become BANK_CARD entities.

        The extractor does not infer issuer, owner, balance, account
        status or whether the number corresponds to a live card.
        """

        results: list[dict[str, Any]] = []

        url_ranges = [
            match.span()
            for match in self.URL_PATTERN.finditer(text)
        ]

        for match in self.BANK_CARD_PATTERN.finditer(text):
            if self._range_overlaps(
                match.span(),
                url_ranges,
            ):
                continue

            value = match.group(0).strip()
            normalized = self.normalizer.normalize_bank_card(value)

            if not self._is_bank_card_candidate(
                text=text,
                value=value,
                normalized=normalized,
                span=match.span(),
            ):
                continue

            has_context = self._has_bank_card_context(
                text=text,
                span=match.span(),
            )
            formatting = self._bank_card_formatting(value)

            confidence = 0.97
            if has_context:
                confidence = 0.99
            elif formatting != "compact":
                confidence = 0.98

            results.append(
                self.create_entity(
                    EntityType.BANK_CARD,
                    value,
                    confidence=confidence,
                    metadata={
                        "identifier_kind": "bank_card",
                        "validation": "luhn",
                        "digit_count": len(normalized),
                        "formatting": formatting,
                        "payment_context": has_context,
                        "classification": (
                            "context_disambiguated"
                            if len(normalized) <= 15
                            else "outside_phone_range"
                        ),
                    },
                )
            )

        return results

    def _is_bank_card_candidate(
        self,
        *,
        text: str,
        value: str,
        normalized: str,
        span: tuple[int, int],
    ) -> bool:
        """Return True when a Luhn-valid value is safe to classify."""

        if not self.validate_bank_card(normalized):
            return False

        digit_count = len(normalized)

        # 16--19 digit values are outside the E.164 phone-number range.
        if digit_count >= 16:
            return True

        # 13--15 digits can be either a card number or a legitimate
        # international phone number.  Luhn alone is not enough.
        return self._has_bank_card_context(
            text=text,
            span=span,
        )

    def _has_bank_card_context(
        self,
        *,
        text: str,
        span: tuple[int, int],
        radius: int = 48,
    ) -> bool:
        """Look for a nearby card/payment label without inferring more."""

        start, end = span
        context_start = max(0, start - radius)
        context_end = min(len(text), end + radius)
        context_text = text[context_start:context_end]

        return bool(
            self.BANK_CARD_CONTEXT_PATTERN.search(context_text)
        )

    @staticmethod
    def _bank_card_formatting(
        value: str,
    ) -> str:
        has_spaces = any(character.isspace() for character in value)
        has_hyphens = "-" in value

        if has_spaces and has_hyphens:
            return "mixed"
        if has_spaces:
            return "spaced"
        if has_hyphens:
            return "hyphenated"
        return "compact"

    @staticmethod
    def validate_ip(
        value: str,
    ) -> bool:

        try:

            ipaddress.ip_address(
                value
            )

            return True

        except ValueError:

            return False

    # ==========================================================
    # Hash
    # ==========================================================

    def extract_hashes(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                EntityType.OTHER,
                value,
                confidence=0.9,
                metadata={
                    "identifier_kind": "hash",
                },
            )
            for value
            in self.HASH_PATTERN.findall(text)
        ]

    # ==========================================================
    # Entity construction
    # ==========================================================

    def create_entity(
        self,
        entity_type: EntityType,
        value: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized = self.normalizer.normalize(
            entity_type,
            value,
        )

        return {
            "type": entity_type.value,
            "value": value.strip(),
            "normalized": normalized,
            "confidence": confidence,
            "metadata": metadata or {},
        }

    # ==========================================================
    # Deduplication
    # ==========================================================

    @staticmethod
    def merge_duplicates(
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        unique: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        for entity in entities:

            key = (
                str(entity["type"]),
                str(entity["normalized"]),
            )

            existing = unique.get(key)

            if (
                existing is None
                or float(
                    entity["confidence"]
                )
                > float(
                    existing["confidence"]
                )
            ):

                unique[key] = entity

        return list(
            unique.values()
        )

    # ==========================================================
    # Statistics / export
    # ==========================================================

    @staticmethod
    def build_statistics(
        entities: list[dict[str, Any]],
    ) -> dict[str, Any]:

        counter = Counter(
            entity["type"]
            for entity in entities
        )

        return {
            "total": len(entities),
            "types": dict(counter),
        }

    def export(
        self,
        entities: list[dict[str, Any]],
    ) -> dict[str, Any]:

        return {
            "entities": entities,
            "statistics": (
                self.build_statistics(
                    entities
                )
            ),
        }

    # ==========================================================
    # Context helpers
    # ==========================================================

    @staticmethod
    def _range_overlaps(
        candidate: tuple[int, int],
        ranges: list[tuple[int, int]],
    ) -> bool:

        start, end = candidate

        return any(
            start < range_end
            and end > range_start
            for range_start, range_end
            in ranges
        )

    @staticmethod
    def _domain_is_email_component(
        text: str,
        domain: str,
    ) -> bool:

        for match in re.finditer(
            re.escape(domain),
            text,
            flags=re.IGNORECASE,
        ):

            start = match.start()

            if (
                start > 0
                and text[start - 1] == "@"
            ):

                return True

        return False

    @staticmethod
    def validate_bank_card(
        value: str,
    ) -> bool:

        if not value.isdigit():
            return False

        if not (
            13
            <= len(value)
            <= 19
        ):
            return False

        # Reject obviously meaningless repeated sequences.
        if len(set(value)) == 1:
            return False

        total = 0
        parity = (
            len(value)
            % 2
        )

        for index, character in enumerate(
            value
        ):

            digit = int(
                character
            )

            if (
                index % 2
                == parity
            ):

                digit *= 2

                if digit > 9:
                    digit -= 9

            total += digit

        return (
            total % 10
            == 0
        )
