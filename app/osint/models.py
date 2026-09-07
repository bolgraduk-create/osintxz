"""
OSINT models.

Shared models used by every
OSINT connector.

Responsibilities:

- investigation target
- structured investigation request
- target types
- connector requests

Does NOT:

- store results
- call tools
- access database
- select connectors
- normalize user input
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import date
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

    Represents one concrete value that can be
    passed to compatible OSINT connectors.

    Examples:

    - username
    - email address
    - phone number
    - domain
    - IP address
    - person name
    """

    target_type: OsintTargetType

    value: str

    label: str | None = None

    description: str | None = None

    case_id: str | None = None


@dataclass(slots=True)
class OsintInvestigationRequest:
    """
    Structured OSINT investigation request.

    Represents all information entered by the user
    in the OSINT workspace.

    One investigation request may later be converted
    into multiple independent OsintTarget objects.

    Empty fields are allowed. The user only needs to
    provide information that is currently known.
    """

    # ==========================================================
    # Investigation context
    # ==========================================================

    case_id: str | None = None

    title: str | None = None

    description: str | None = None

    # ==========================================================
    # Person identity
    # ==========================================================

    first_name: str | None = None

    middle_name: str | None = None

    last_name: str | None = None

    birth_date: date | None = None

    # ==========================================================
    # Online identities
    # ==========================================================

    usernames: list[str] = field(
        default_factory=list
    )

    emails: list[str] = field(
        default_factory=list
    )

    phones: list[str] = field(
        default_factory=list
    )

    # ==========================================================
    # Location information
    # ==========================================================

    country: str | None = None

    region: str | None = None

    city: str | None = None

    postal_code: str | None = None

    address: str | None = None

    # ==========================================================
    # Organizations
    # ==========================================================

    organizations: list[str] = field(
        default_factory=list
    )

    # ==========================================================
    # Network and web targets
    # ==========================================================

    domains: list[str] = field(
        default_factory=list
    )

    urls: list[str] = field(
        default_factory=list
    )

    ip_addresses: list[str] = field(
        default_factory=list
    )

    hashes: list[str] = field(
        default_factory=list
    )

    # ==========================================================
    # Local artifacts
    # ==========================================================

    file_paths: list[str] = field(
        default_factory=list
    )

    image_paths: list[str] = field(
        default_factory=list
    )

    # ==========================================================
    # Additional search context
    # ==========================================================

    keywords: list[str] = field(
        default_factory=list
    )

    notes: str | None = None


@dataclass(slots=True)
class ConnectorRequest:
    """
    Request passed to connector.

    Contains one concrete target and common
    execution options shared by connectors.
    """

    target: OsintTarget

    timeout: int = 300

    use_cache: bool = True

    save_raw_output: bool = False

    include_metadata: bool = True

    include_related: bool = True