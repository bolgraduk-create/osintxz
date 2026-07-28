"""
Tests for EvidenceMigrationService.
"""

from unittest.mock import MagicMock


from app.services.evidence_migration_service import (
    EvidenceMigrationService,
)



def test_service_creation():

    session = MagicMock()


    service = EvidenceMigrationService(
        session
    )


    assert (
        service.session
        ==
        session
    )