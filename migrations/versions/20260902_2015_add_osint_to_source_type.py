"""add OSINT to source_type enum

Revision ID: 20260902_2015
Revises: 20260830_1006
Create Date: 2026-09-02
"""

from __future__ import annotations

from alembic import op


revision = "20260902_2015"
down_revision = "20260830_1006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL enum additions should be committed before the value is used
    # by later application transactions. Keep the enum DDL isolated.
    with op.get_context().autocommit_block():
        op.execute(
            """
            ALTER TYPE source_type
            ADD VALUE IF NOT EXISTS 'OSINT' BEFORE 'OTHER'
            """
        )


def downgrade() -> None:
    # PostgreSQL cannot remove a single enum label safely with ALTER TYPE.
    # A downgrade after OSINT data exists would require rebuilding the enum
    # and deciding what to do with persisted OSINT rows, which is data-policy
    # sensitive. Fail explicitly instead of silently corrupting provenance.
    raise RuntimeError(
        "Downgrade of revision 20260902_2015 is intentionally blocked: "
        "removing source_type.OSINT requires an explicit data migration."
    )
