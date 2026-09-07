"""Read-only schema drift check for the OSINTXZ PostgreSQL database.

The script compares the live database with SQLAlchemy ``Base.metadata``
without modifying the database or requiring an existing Alembic version row.
It also verifies the pgvector extension and the PostgreSQL ``entity_type``
enum labels because enum-value drift is not always detected by Alembic's
normal autogenerate comparison.
"""

from __future__ import annotations

from pprint import pformat

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy import pool

import app.models  # noqa: F401
from app.core.config import settings
from app.database.base import Base
from app.models.entity import EntityType


def main() -> int:
    """Compare the configured database with the ORM schema."""

    engine = create_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        pool_pre_ping=True,
    )

    failures: list[str] = []

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)

            live_tables = set(
                inspector.get_table_names(schema="public")
            )
            model_tables = set(Base.metadata.tables)

            missing_tables = sorted(model_tables - live_tables)
            extra_tables = sorted(
                table
                for table in live_tables - model_tables
                if table != "alembic_version"
            )

            if missing_tables:
                failures.append(
                    "Tables missing from database: "
                    + ", ".join(missing_tables)
                )

            if extra_tables:
                failures.append(
                    "Tables present only in database: "
                    + ", ".join(extra_tables)
                )

            vector_enabled = bool(
                connection.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM pg_extension
                            WHERE extname = 'vector'
                        )
                        """
                    )
                ).scalar_one()
            )

            if not vector_enabled:
                failures.append(
                    "PostgreSQL extension 'vector' is not enabled."
                )

            live_entity_type = list(
                connection.execute(
                    text(
                        """
                        SELECT e.enumlabel
                        FROM pg_type AS t
                        JOIN pg_enum AS e
                          ON t.oid = e.enumtypid
                        JOIN pg_namespace AS n
                          ON n.oid = t.typnamespace
                        WHERE t.typname = 'entity_type'
                          AND n.nspname = 'public'
                        ORDER BY e.enumsortorder
                        """
                    )
                ).scalars()
            )

            expected_entity_type = [
                member.name
                for member in EntityType
            ]

            if live_entity_type != expected_entity_type:
                failures.append(
                    "entity_type enum mismatch:\n"
                    f"  database={live_entity_type}\n"
                    f"  models={expected_entity_type}"
                )

            migration_context = MigrationContext.configure(
                connection,
                opts={
                    "compare_type": True,
                    "compare_server_default": True,
                },
            )

            metadata_diffs = compare_metadata(
                migration_context,
                Base.metadata,
            )

            if metadata_diffs:
                failures.append(
                    "Alembic metadata differences:\n"
                    + pformat(metadata_diffs, width=120)
                )

    finally:
        engine.dispose()

    print("======================================")
    print("OSINTXZ SCHEMA DRIFT CHECK")
    print("======================================")

    if failures:
        print("RESULT: FAIL")
        print()

        for index, failure in enumerate(failures, start=1):
            print(f"[{index}] {failure}")
            print()

        return 1

    print("RESULT: PASS")
    print("Database schema matches Base.metadata.")
    print("pgvector is enabled.")
    print("entity_type enum matches EntityType.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
