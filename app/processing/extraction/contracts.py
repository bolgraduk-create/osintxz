"""
Unified extraction contracts.

These contracts are source-agnostic. Telegram, documents, OCR,
transcripts, registries and future collectors can all describe
where extracted information came from without coupling the
extraction core to a specific importer.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any
from uuid import UUID

from app.models.entity import EntityType


class ExtractionObjectType(str, Enum):
    """Supported source object kinds for extraction provenance."""

    MESSAGE = "message"
    DOCUMENT = "document"
    EVIDENCE = "evidence"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class ExtractionOrigin:
    """Describe the object from which a candidate was extracted."""

    case_id: UUID
    object_type: ExtractionObjectType
    source_id: UUID | None = None
    object_id: UUID | None = None
    evidence_id: UUID | None = None
    external_id: str | None = None
    sender: str | None = None
    chat_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Serialize provenance into JSON-compatible metadata."""

        return {
            "object_type": self.object_type.value,
            "object_id": (
                str(self.object_id)
                if self.object_id is not None
                else None
            ),
            "source_id": (
                str(self.source_id)
                if self.source_id is not None
                else None
            ),
            "evidence_id": (
                str(self.evidence_id)
                if self.evidence_id is not None
                else None
            ),
            "external_id": self.external_id,
            "sender": self.sender,
            "chat_name": self.chat_name,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    """One normalized entity candidate produced by an extractor."""

    entity_type: EntityType
    value: str
    normalized_value: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
