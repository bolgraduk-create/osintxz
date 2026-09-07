"""
Database initialization.

Responsible for creating database extensions
and tables during first application startup.

This module must be executed only after
all ORM models are imported.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy import text

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
    FaceEmbedding,
    FaceProfile,
    Message,
    Note,
    Project,
    Relationship,
    Report,
    SearchEmbedding,
    SearchIndex,
    Source,
    TimelineEvent,
    Workspace,
    WorkspaceMembership,
    SearchSemanticChunk,
    SearchSemanticChunkEmbedding,
)


# ==========================================================
# Extensions
# ==========================================================


def init_extensions(
    db_engine: Engine = engine,
) -> None:
    """
    Enable PostgreSQL extensions required
    by the application.

    Extensions are enabled before ORM tables
    are created because some models depend
    on extension-provided data types.
    """

    with db_engine.begin() as connection:

        connection.execute(
            text(
                "CREATE EXTENSION IF NOT EXISTS vector"
            )
        )


# ==========================================================
# Database initialization
# ==========================================================


def init_database(
    db_engine: Engine = engine,
) -> None:
    """
    Initialize required extensions
    and create all database tables.

    Existing tables are not modified.
    Missing tables are created.
    """

    init_extensions(
        db_engine
    )

    Base.metadata.create_all(
        bind=db_engine,
    )


# ==========================================================
# Database removal
# ==========================================================


def drop_database(
    db_engine: Engine = engine,
) -> None:
    """
    Drop all application database tables.

    PostgreSQL extensions are intentionally
    preserved.

    Used only for development and tests.
    """

    Base.metadata.drop_all(
        bind=db_engine,
    )


# ==========================================================
# Entry point
# ==========================================================


if __name__ == "__main__":

    print(
        "Initializing database..."
    )

    init_database()

    print(
        "Database initialized successfully."
    )