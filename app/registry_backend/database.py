"""Database/session boundary owned by Registry Backend infrastructure."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.registry_backend.settings import backend_settings


def _make_engine(url: str, *, application_name: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={"application_name": application_name},
    )


@lru_cache(maxsize=1)
def registry_read_engine() -> Engine:
    return _make_engine(
        backend_settings.read_database_url,
        application_name="osintxz-registry-api",
    )


@lru_cache(maxsize=1)
def registry_ingestion_engine() -> Engine:
    return _make_engine(
        backend_settings.ingestion_database_url,
        application_name="osintxz-registry-ingestion",
    )


def create_registry_read_session() -> Session:
    factory = sessionmaker(
        bind=registry_read_engine(),
        autoflush=False,
        autocommit=False,
    )
    return factory()


def create_registry_ingestion_session() -> Session:
    factory = sessionmaker(
        bind=registry_ingestion_engine(),
        autoflush=False,
        autocommit=False,
    )
    return factory()
