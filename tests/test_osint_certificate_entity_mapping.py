from __future__ import annotations

import pytest

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.pivot_candidates import (
    OsintPivotCandidatePolicy,
)
from app.osint.result import OsintFinding


@pytest.mark.parametrize(
    ("raw", "expected_type", "expected_value"),
    [
        (
            "*.example.com",
            EntityType.DOMAIN,
            "example.com",
        ),
        (
            "example.com",
            EntityType.DOMAIN,
            "example.com",
        ),
        (
            "www.example.com",
            EntityType.DOMAIN,
            "www.example.com",
        ),
        (
            "user@example.com",
            EntityType.EMAIL,
            "user@example.com",
        ),
    ],
)
def test_certificate_identifiers_become_safe_entities(
    raw,
    expected_type,
    expected_value,
):
    finding = OsintFinding(
        category="certificate",
        value=raw,
        source="crt.sh",
        confidence=0.95,
    )

    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(
            finding
        )
    )

    assert candidates == (
        (
            expected_type,
            expected_value,
            0.95,
        ),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "AS207960 Test Intermediate - example.com",
        "Example Corporation",
        "https://example.com/",
        "not a domain.example.com extra",
        "localhost",
        "-bad.example.com",
        "bad-.example.com",
        "example.123",
        "user @example.com",
    ],
)
def test_arbitrary_certificate_text_never_becomes_entity(
    raw,
):
    finding = OsintFinding(
        category="certificate",
        value=raw,
        source="crt.sh",
    )

    assert (
        OsintFindingPersistenceService
        ._entity_candidates(
            finding
        )
        == ()
    )


def test_multiline_certificate_values_are_deduplicated():
    finding = OsintFinding(
        category="certificate",
        value="*.example.com\nexample.com\nwww.example.com",
        source="crt.sh",
        confidence=0.8,
    )

    candidates = (
        OsintFindingPersistenceService
        ._entity_candidates(
            finding
        )
    )

    assert candidates == (
        (
            EntityType.DOMAIN,
            "example.com",
            0.8,
        ),
        (
            EntityType.DOMAIN,
            "www.example.com",
            0.8,
        ),
    )


def test_certificate_evidence_is_metadata():
    finding = OsintFinding(
        category="certificate",
        value="www.example.com",
        source="crt.sh",
    )

    assert (
        OsintFindingPersistenceService
        ._evidence_type(
            finding
        )
        is EvidenceType.METADATA
    )


@pytest.mark.parametrize(
    ("entity_type", "expected"),
    [
        (
            EntityType.DOMAIN,
            "domain",
        ),
        (
            EntityType.EMAIL,
            "email",
        ),
    ],
)
def test_certificate_entity_types_are_pivot_supported(
    entity_type,
    expected,
):
    policy = OsintPivotCandidatePolicy()

    target_type = policy.target_type_for_entity(
        entity_type
    )

    assert target_type is not None
    assert target_type.value == expected
