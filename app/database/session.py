"""
Database engine and session management.

This module is the only place where SQLAlchemy Engine
and Session are created.

All modules in the project must import database sessions
only from here.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# ==========================================================
# Engine
# ==========================================================

engine: Engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,
)


# ==========================================================
# Session factory
# ==========================================================

SessionFactory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ==========================================================
# FastAPI dependency
# ==========================================================

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.

    Example:

        def endpoint(
            db: Session = Depends(get_db)
        ):
            ...
    """

    session = SessionFactory()

    try:
        yield session

        session.commit()

    except Exception:

        session.rollback()

        raise

    finally:

        session.close()


# ==========================================================
# Manual session
# ==========================================================

def create_session() -> Session:
    """
    Returns a manually managed session.

    Used by:

    - CLI
    - Celery
    - scripts
    - tests
    """

    return SessionFactory()


# ==========================================================
# Health check
# ==========================================================

def check_database_connection() -> bool:
    """
    Returns True if database connection is available.
    """

    try:

        with engine.connect() as connection:

            connection.exec_driver_sql("SELECT 1")

        return True

    except Exception:

        return False