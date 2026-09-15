"""add Ukraine EDRSR registry cache foundation

Revision ID: 20260913_2030
Revises: 20260913_1505
Create Date: 2026-09-13 20:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260913_2030"
down_revision = "20260913_1505"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registry_ua_edrsr_decisions",
        sa.Column("dataset_year", sa.Integer(), nullable=False),
        sa.Column("generation", sa.String(length=64), nullable=False),
        sa.Column("doc_id", sa.BigInteger(), nullable=False),
        sa.Column("court_code", sa.String(length=32), nullable=True),
        sa.Column("court_name", sa.String(length=1024), nullable=True),
        sa.Column("instance_name", sa.String(length=512), nullable=True),
        sa.Column("region_name", sa.String(length=512), nullable=True),
        sa.Column("judgment_code", sa.String(length=32), nullable=True),
        sa.Column("judgment_name", sa.String(length=512), nullable=True),
        sa.Column("justice_kind", sa.String(length=32), nullable=True),
        sa.Column("justice_kind_name", sa.String(length=512), nullable=True),
        sa.Column("category_code", sa.String(length=64), nullable=True),
        sa.Column("category_name", sa.Text(), nullable=True),
        sa.Column("cause_num", sa.String(length=512), nullable=True),
        sa.Column("cause_num_normalized", sa.String(length=512), nullable=True),
        sa.Column("adjudication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("judge", sa.String(length=2048), nullable=True),
        sa.Column("doc_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("date_publ", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_dataset_id", sa.String(length=128), nullable=True),
        sa.Column("source_resource_id", sa.String(length=128), nullable=True),
        sa.Column("source_modified_at", sa.String(length=128), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("raw_reference", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registry_ua_edrsr_decisions")),
        sa.UniqueConstraint(
            "dataset_year",
            "generation",
            "doc_id",
            name="uq_registry_ua_edrsr_year_generation_doc",
        ),
    )
    for column in (
        "dataset_year", "generation", "court_code", "judgment_code",
        "justice_kind", "category_code", "cause_num_normalized",
        "adjudication_date", "status",
    ):
        op.create_index(
            op.f(f"ix_registry_ua_edrsr_decisions_{column}"),
            "registry_ua_edrsr_decisions",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_registry_ua_edrsr_generation_case",
        "registry_ua_edrsr_decisions",
        ["generation", "cause_num_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edrsr_year_generation_case",
        "registry_ua_edrsr_decisions",
        ["dataset_year", "generation", "cause_num_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edrsr_generation_doc_id",
        "registry_ua_edrsr_decisions",
        ["generation", "doc_id"],
        unique=False,
    )

    op.create_table(
        "registry_ua_edrsr_sync_state",
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("dataset_year", sa.Integer(), nullable=False),
        sa.Column("active_generation", sa.String(length=64), nullable=True),
        sa.Column("pending_generation", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("dataset_modified_at", sa.String(length=128), nullable=True),
        sa.Column("resource_modified_at", sa.String(length=128), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("record_count", sa.BigInteger(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registry_ua_edrsr_sync_state")),
        sa.UniqueConstraint(
            "source_code",
            "dataset_year",
            name="uq_registry_ua_edrsr_sync_source_year",
        ),
    )
    op.create_index(
        op.f("ix_registry_ua_edrsr_sync_state_dataset_year"),
        "registry_ua_edrsr_sync_state",
        ["dataset_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_registry_ua_edrsr_sync_state_active_generation"),
        "registry_ua_edrsr_sync_state",
        ["active_generation"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_registry_ua_edrsr_sync_state_active_generation"),
        table_name="registry_ua_edrsr_sync_state",
    )
    op.drop_index(
        op.f("ix_registry_ua_edrsr_sync_state_dataset_year"),
        table_name="registry_ua_edrsr_sync_state",
    )
    op.drop_table("registry_ua_edrsr_sync_state")

    op.drop_index("ix_registry_ua_edrsr_generation_doc_id", table_name="registry_ua_edrsr_decisions")
    op.drop_index("ix_registry_ua_edrsr_year_generation_case", table_name="registry_ua_edrsr_decisions")
    op.drop_index("ix_registry_ua_edrsr_generation_case", table_name="registry_ua_edrsr_decisions")
    for column in reversed((
        "dataset_year", "generation", "court_code", "judgment_code",
        "justice_kind", "category_code", "cause_num_normalized",
        "adjudication_date", "status",
    )):
        op.drop_index(
            op.f(f"ix_registry_ua_edrsr_decisions_{column}"),
            table_name="registry_ua_edrsr_decisions",
        )
    op.drop_table("registry_ua_edrsr_decisions")
