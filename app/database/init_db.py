"""
Database initialization.

Responsible for creating database tables
during first application startup.

This module must be executed only after
all ORM models are imported.
"""

from __future__ import annotations

from sqlalchemy import Engine

from app.database.base import Base
from app.database.session import engine

# Import every model so SQLAlchemy metadata
# knows about every table.
from app.models import (
    Account,
    AIAnalysis,
    Artifact,
    Case,
    Document,
    Entity,
    EntityMerge,
    Evidence,
    EvidenceEntity,
    Message,
    Note,
    Project,
    Relationship,
    Report,
    SearchIndex,
    Source,
    TimelineEvent,
    Workspace,
    WorkspaceMembership,
)


def init_database(
    db_engine: Engine = engine,
) -> None:
    """
    Create all database tables.

    Existing tables are not modified.
    """

    Base.metadata.create_all(
        bind=db_engine,
    )


def drop_database(
    db_engine: Engine = engine,
) -> None:
    """
    Drop all database tables.

    Used only for development and tests.
    """

    Base.metadata.drop_all(
        bind=db_engine,
    )


if __name__ == "__main__":

    print(
        "Initializing database..."
    )

    init_database()

    print(
        "Database initialized successfully."
    )