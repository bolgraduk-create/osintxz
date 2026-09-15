"""add Ukraine EDR local registry mirror

Revision ID: 20260913_1505
Revises: 20260902_2015
Create Date: 2026-09-13 15:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260913_1505"
down_revision = "20260902_2015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registry_ua_edr_subjects",
        sa.Column("generation", sa.String(length=64), nullable=False),
        sa.Column("subject_kind", sa.String(length=32), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=1024), nullable=False),
        sa.Column("name_normalized", sa.String(length=1024), nullable=False),
        sa.Column("short_name", sa.String(length=1024), nullable=True),
        sa.Column("registration_id", sa.String(length=64), nullable=True),
        sa.Column("legal_form", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=512), nullable=True),
        sa.Column("registration_info", sa.Text(), nullable=True),
        sa.Column("termination_info", sa.Text(), nullable=True),
        sa.Column("estate_manager", sa.Text(), nullable=True),
        sa.Column("family_farm", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("source_resource_id", sa.String(length=128), nullable=True),
        sa.Column("source_modified_at", sa.String(length=128), nullable=True),
        sa.Column("raw_reference", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registry_ua_edr_subjects")),
        sa.UniqueConstraint(
            "generation",
            "subject_kind",
            "record_id",
            name="uq_registry_ua_edr_subject_generation_kind_record",
        ),
    )
    op.create_index(
        "ix_registry_ua_edr_subjects_generation",
        "registry_ua_edr_subjects",
        ["generation"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_subjects_subject_kind",
        "registry_ua_edr_subjects",
        ["subject_kind"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_subjects_name_normalized",
        "registry_ua_edr_subjects",
        ["name_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_subjects_registration_id",
        "registry_ua_edr_subjects",
        ["registration_id"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_subjects_status",
        "registry_ua_edr_subjects",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_generation_registration",
        "registry_ua_edr_subjects",
        ["generation", "registration_id"],
        unique=False,
    )
    op.create_index(
        "ix_registry_ua_edr_generation_kind_name",
        "registry_ua_edr_subjects",
        ["generation", "subject_kind", "name_normalized"],
        unique=False,
    )

    op.create_table(
        "registry_ua_edr_sync_state",
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("active_generation", sa.String(length=64), nullable=True),
        sa.Column("pending_generation", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dataset_id", sa.String(length=128), nullable=True),
        sa.Column("dataset_modified_at", sa.String(length=128), nullable=True),
        sa.Column("uo_resource_id", sa.String(length=128), nullable=True),
        sa.Column("fop_resource_id", sa.String(length=128), nullable=True),
        sa.Column("uo_record_count", sa.Integer(), nullable=False),
        sa.Column("fop_record_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_registry_ua_edr_sync_state")),
        sa.UniqueConstraint("source_code", name="uq_registry_ua_edr_sync_state_source_code"),
    )
    op.create_index(
        "ix_registry_ua_edr_sync_state_active_generation",
        "registry_ua_edr_sync_state",
        ["active_generation"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_registry_ua_edr_sync_state_active_generation",
        table_name="registry_ua_edr_sync_state",
    )
    op.drop_table("registry_ua_edr_sync_state")

    op.drop_index("ix_registry_ua_edr_generation_kind_name", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_generation_registration", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_subjects_status", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_subjects_registration_id", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_subjects_name_normalized", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_subjects_subject_kind", table_name="registry_ua_edr_subjects")
    op.drop_index("ix_registry_ua_edr_subjects_generation", table_name="registry_ua_edr_subjects")
    op.drop_table("registry_ua_edr_subjects")
