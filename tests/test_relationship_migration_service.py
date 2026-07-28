"""
Tests for RelationshipMigrationService.
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.relationship_migration_service import (
    RelationshipMigrationService,
)


def test_service_creation():

    session = MagicMock()


    service = RelationshipMigrationService(
        session
    )


    assert (
        service.session
        ==
        session
    )