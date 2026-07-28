"""
Common collector models.

Every collector returns CollectedItem objects.

Responsibilities:

- unified collection format
- common metadata
- source abstraction
"""

from __future__ import annotations

from dataclasses import dataclass, field

from datetime import datetime

from enum import Enum

from typing import Any


class CollectedItemType(str, Enum):
    """
    Supported collected item types.
    """

    MESSAGE = "message"

    DOCUMENT = "document"

    IMAGE = "image"

    VIDEO = "video"

    AUDIO = "audio"

    LOCATION = "location"

    CONTACT = "contact"

    ACCOUNT = "account"

    WEBSITE = "website"

    OTHER = "other"


@dataclass(slots=True)
class CollectedItem:
    """
    Universal collected object.
    """

    source: str

    item_type: CollectedItemType

    content: str

    timestamp: datetime | None = None

    title: str | None = None

    author: str | None = None

    external_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )