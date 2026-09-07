"""
Identifier extraction adapter.

Wraps the existing EntityAnalyzer behind a stable, typed extraction
contract. The analyzer remains responsible for pattern detection and
identifier-specific validation; callers no longer depend on its raw
``dict`` payload format.
"""

from __future__ import annotations

from app.analysis.analyzers.entity_analyzer import EntityAnalyzer
from app.entity_resolution.normalizer import EntityNormalizer
from app.models.entity import EntityType
from app.processing.extraction.contracts import ExtractionCandidate


class IdentifierExtractor:
    """Source-agnostic textual identifier extractor."""

    name = "EntityAnalyzer"

    def __init__(
        self,
        *,
        analyzer: EntityAnalyzer | None = None,
        normalizer: EntityNormalizer | None = None,
    ) -> None:
        self.normalizer = normalizer or EntityNormalizer()
        self.analyzer = analyzer or EntityAnalyzer(
            normalizer=self.normalizer,
        )

    def extract(
        self,
        text: str | None,
    ) -> list[ExtractionCandidate]:
        """Extract normalized identifier candidates from text."""

        if text is None:
            return []

        normalized_text = str(text)

        if not normalized_text.strip():
            return []

        candidates: list[ExtractionCandidate] = []

        for payload in self.analyzer.analyze(normalized_text):
            if not isinstance(payload, dict):
                continue

            try:
                entity_type = EntityType(
                    str(payload.get("type", "")).strip().lower()
                )
            except ValueError:
                continue

            value = str(payload.get("value", "")).strip()
            normalized_value = str(
                payload.get("normalized", "")
            ).strip()

            if not value or not normalized_value:
                continue

            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            try:
                confidence = float(payload.get("confidence", 1.0))
            except (TypeError, ValueError):
                confidence = 1.0

            confidence = max(0.0, min(1.0, confidence))

            candidates.append(
                ExtractionCandidate(
                    entity_type=entity_type,
                    value=value,
                    normalized_value=normalized_value,
                    confidence=confidence,
                    metadata=dict(metadata),
                )
            )

        return candidates
