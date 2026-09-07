"""Enforce unique EvidenceEntity provenance links.

Revision ID: 20260830_1006
Revises: 105eefbcbdb6
Create Date: 2026-08-30
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

from alembic import op


revision: str = "20260830_1006"
down_revision: Union[str, Sequence[str], None] = "105eefbcbdb6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEX_NAME = "ix_evidence_entities_unique"
_TABLE_NAME = "evidence_entities"


def upgrade() -> None:
    """Deduplicate old links and enforce one link per evidence/entity pair."""

    # EvidenceEntity contains no occurrence-specific payload beyond the
    # pair itself, so duplicate rows are semantically redundant. Keep the
    # earliest row before replacing the historical non-unique index.
    op.execute(
        """
        WITH ranked_links AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY evidence_id, entity_id
                    ORDER BY created_at ASC, id ASC
                ) AS row_number
            FROM evidence_entities
        )
        DELETE FROM evidence_entities
        WHERE id IN (
            SELECT id
            FROM ranked_links
            WHERE row_number > 1
        )
        """
    )

    op.drop_index(
        _INDEX_NAME,
        table_name=_TABLE_NAME,
    )

    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        ["evidence_id", "entity_id"],
        unique=True,
    )


def downgrade() -> None:
    """Restore the historical non-unique EvidenceEntity index."""

    op.drop_index(
        _INDEX_NAME,
        table_name=_TABLE_NAME,
    )

    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        ["evidence_id", "entity_id"],
        unique=False,
    )
