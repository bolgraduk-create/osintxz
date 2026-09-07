"""Enable pgvector extension.

Revision ID: 20260830_0000
Revises: None
Create Date: 2026-08-30
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

from alembic import op


revision: str = "20260830_0000"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable the PostgreSQL vector extension."""

    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )


def downgrade() -> None:
    """Keep pgvector installed.

    The extension may own data types used by application tables and may be
    shared by other objects.  Removing it automatically during downgrade is
    therefore intentionally unsafe and is not performed.
    """

    pass
