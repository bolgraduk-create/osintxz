"""Unified source-agnostic extraction layer."""

from app.processing.extraction.contracts import ExtractionCandidate
from app.processing.extraction.contracts import ExtractionObjectType
from app.processing.extraction.contracts import ExtractionOrigin
from app.processing.extraction.identifier_extractor import IdentifierExtractor

__all__ = [
    "ExtractionCandidate",
    "ExtractionObjectType",
    "ExtractionOrigin",
    "IdentifierExtractor",
]
