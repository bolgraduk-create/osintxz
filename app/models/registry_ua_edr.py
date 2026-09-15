"""Local mirror models for Ukraine's public EDR open-data export.

The mirror is global application infrastructure, not investigation evidence.
Only records selected through Registry Intelligence are copied into a Case as
Source/Evidence/Entity objects.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import BaseModel


class UaEdrSubject(BaseModel):
    __tablename__ = "registry_ua_edr_subjects"
    __table_args__ = (
        UniqueConstraint(
            "generation",
            "subject_kind",
            "record_id",
            name="uq_registry_ua_edr_subject_generation_kind_record",
        ),
        Index(
            "ix_registry_ua_edr_generation_registration",
            "generation",
            "registration_id",
        ),
        Index(
            "ix_registry_ua_edr_generation_kind_name",
            "generation",
            "subject_kind",
            "name_normalized",
        ),
    )

    generation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    registration_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    legal_form: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    registration_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    termination_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    estate_manager: Mapped[str | None] = mapped_column(Text, nullable=True)
    family_farm: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_modified_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UaEdrSyncState(BaseModel):
    __tablename__ = "registry_ua_edr_sync_state"
    __table_args__ = (
        UniqueConstraint("source_code", name="uq_registry_ua_edr_sync_state_source_code"),
    )

    source_code: Mapped[str] = mapped_column(String(64), nullable=False)
    active_generation: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pending_generation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="empty")
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_modified_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uo_resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fop_resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uo_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    fop_record_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
