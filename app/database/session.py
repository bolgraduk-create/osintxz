"""
Database session management.

Provides SQLAlchemy sessions
for application services and tests.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)


SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_session() -> Session:
    """
    Create new database session.
    """

    return SessionFactory()


def get_session() -> Generator[Session, None, None]:
    """
    Provide database session.

    Used by:
    - tests
    - services
    - dependency injection
    """

    session = create_session()

    try:
        yield session

    finally:
        session.close()