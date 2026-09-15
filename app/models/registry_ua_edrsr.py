"""Server-side cache models for Ukraine's Unified State Register of Court Decisions.

The desktop application never mirrors this national dataset. These tables belong
on the Registry Backend database and store one active snapshot per source year.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import BaseModel


class UaEdrsrDecision(BaseModel):
    __tablename__ = "registry_ua_edrsr_decisions"
    __table_args__ = (
        UniqueConstraint(
            "dataset_year",
            "generation",
            "doc_id",
            name="uq_registry_ua_edrsr_year_generation_doc",
        ),
        Index(
            "ix_registry_ua_edrsr_generation_case",
            "generation",
            "cause_num_normalized",
        ),
        Index(
            "ix_registry_ua_edrsr_year_generation_case",
            "dataset_year",
            "generation",
            "cause_num_normalized",
        ),
        Index(
            "ix_registry_ua_edrsr_generation_doc_id",
            "generation",
            "doc_id",
        ),
    )

    dataset_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    generation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doc_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    court_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    court_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    instance_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    region_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    judgment_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    judgment_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    justice_kind: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    justice_kind_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause_num: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cause_num_normalized: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    adjudication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    receipt_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    judge: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    doc_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    date_publ: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_modified_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UaEdrsrSyncState(BaseModel):
    __tablename__ = "registry_ua_edrsr_sync_state"
    __table_args__ = (
        UniqueConstraint(
            "source_code",
            "dataset_year",
            name="uq_registry_ua_edrsr_sync_source_year",
        ),
    )

    source_code: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    active_generation: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pending_generation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="empty")
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_modified_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resource_modified_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    record_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
