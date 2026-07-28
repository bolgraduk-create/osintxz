"""
Tests for EvidenceLinkService.
"""

from unittest.mock import MagicMock

from app.services.evidence_link_service import (
    EvidenceLinkService,
)


def test_service_creation():

    session = MagicMock()

    service = EvidenceLinkService(session)

    assert service.session is session