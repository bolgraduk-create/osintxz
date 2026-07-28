"""
Entity analyzer.

Responsible for extracting,
normalizing and validating entities
from unstructured data.

Architecture:
    Raw Data
        ↓
    Extraction
        ↓
    Normalization
        ↓
    Validation
        ↓
    Deduplication
        ↓
    Statistics
        ↓
    Result
"""

from __future__ import annotations

import re

from collections import Counter

from typing import Any


class EntityAnalyzer:
    """
    Advanced OSINT entity extractor.

    Extracts different types of entities
    from text and returns normalized objects.
    """


    # ==========================================================
    # Regular expressions
    # ==========================================================

    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@"
        r"[A-Za-z0-9.-]+\."
        r"[A-Za-z]{2,}\b"
    )


    URL_PATTERN = re.compile(
        r"https?://"
        r"[^\s]+"
    )


    DOMAIN_PATTERN = re.compile(
        r"\b(?:[a-zA-Z0-9-]+\.)+"
        r"[a-zA-Z]{2,}\b"
    )


    PHONE_PATTERN = re.compile(
        r"\+?\d[\d\s\-\(\)]{7,}\d"
    )


    USERNAME_PATTERN = re.compile(
        r"@[A-Za-z0-9_]{3,32}"
    )


    IPV4_PATTERN = re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    )


    HASH_PATTERN = re.compile(
        r"\b[a-fA-F0-9]{32,64}\b"
    )


    # ==========================================================
    # Main entry point
    # ==========================================================

    def analyze(
        self,
        text: str,
    ) -> list[dict[str, Any]]:
        """
        Analyze text and extract entities.
        """

        entities = []


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


        entities = self.normalize_entities(
            entities
        )


        entities = self.merge_duplicates(
            entities
        )


        return entities


    # ==========================================================
    # Email extraction
    # ==========================================================

    def extract_emails(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                "email",
                value,
                confidence=1.0,
            )
            for value in self.EMAIL_PATTERN.findall(text)
        ]


    # ==========================================================
    # URL extraction
    # ==========================================================

    def extract_urls(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                "url",
                value,
                confidence=1.0,
            )
            for value in self.URL_PATTERN.findall(text)
        ]


    # ==========================================================
    # Domain extraction
    # ==========================================================

    def extract_domains(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []


        for domain in self.DOMAIN_PATTERN.findall(text):

            if "@" in domain:
                continue

            results.append(
                self.create_entity(
                    "domain",
                    domain,
                    confidence=0.9,
                )
            )


        return results


    # ==========================================================
    # Phone extraction
    # ==========================================================

    def extract_phone_numbers(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                "phone",
                value,
                confidence=0.8,
            )
            for value in self.PHONE_PATTERN.findall(text)
        ]


    # ==========================================================
    # Username extraction
    # ==========================================================

    def extract_usernames(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                "username",
                value,
                confidence=0.7,
            )
            for value in self.USERNAME_PATTERN.findall(text)
        ]


    # ==========================================================
    # IPv4 extraction
    # ==========================================================

    def extract_ipv4(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        results = []


        for ip in self.IPV4_PATTERN.findall(text):

            if self.validate_ipv4(ip):

                results.append(
                    self.create_entity(
                        "ipv4",
                        ip,
                        confidence=0.95,
                    )
                )


        return results


    def validate_ipv4(
        self,
        ip: str,
    ) -> bool:

        parts = ip.split(".")


        if len(parts) != 4:
            return False


        return all(
            0 <= int(part) <= 255
            for part in parts
        )


    # ==========================================================
    # Hash extraction
    # ==========================================================

    def extract_hashes(
        self,
        text: str,
    ) -> list[dict[str, Any]]:

        return [
            self.create_entity(
                "hash",
                value,
                confidence=0.9,
            )
            for value in self.HASH_PATTERN.findall(text)
        ]


    # ==========================================================
    # Entity utilities
    # ==========================================================

    def create_entity(
        self,
        entity_type: str,
        value: str,
        confidence: float,
    ) -> dict[str, Any]:

        return {
            "type": entity_type,
            "value": value,
            "normalized": value.lower(),
            "confidence": confidence,
            "metadata": {},
        }


    def normalize_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        for entity in entities:

            entity["normalized"] = (
                entity["value"]
                .strip()
                .lower()
            )


        return entities


    def merge_duplicates(
        self,
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        unique = {}

        for entity in entities:

            key = (
                entity["type"],
                entity["normalized"],
            )

            if key not in unique:

                unique[key] = entity


        return list(
            unique.values()
        )


    def build_statistics(
        self,
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
            "statistics": self.build_statistics(
                entities
            ),
        }