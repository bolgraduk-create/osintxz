"""
OSINT models.

Shared models used by every
OSINT connector.

Responsibilities:

- investigation target
- target types
- connector requests

Does NOT:

- store results
- call tools
- access database
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OsintTargetType(str, Enum):
    """
    Supported investigation targets.
    """

    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    URL = "url"
    IP = "ip"
    HASH = "hash"
    PERSON = "person"
    ORGANIZATION = "organization"
    FILE = "file"
    IMAGE = "image"
    LOCATION = "location"


@dataclass(slots=True)
class OsintTarget:
    """
    Universal investigation target.
    """

    target_type: OsintTargetType

    value: str

    label: str | None = None

    description: str | None = None

    case_id: str | None = None


@dataclass(slots=True)
class ConnectorRequest:
    """
    Request passed to connector.
    """

    target: OsintTarget

    timeout: int = 300

    use_cache: bool = True

    save_raw_output: bool = False

    include_metadata: bool = True

    include_related: bool = True