"""Persistence/query boundary for the server-side Ukraine EDR mirror."""
from __future__ import annotations

import json
from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.registry_ua_edr import UaEdrSubject, UaEdrSyncState
from app.registry_intelligence.normalization import normalize_ua_edr_name


UA_EDR_SOURCE_CODE = "ua_edr_business"

# COPY bypasses SQLAlchemy's Python-side UUID default, therefore the primary
# key is supplied explicitly. The column list is static application code: no
# user-controlled identifier is ever interpolated into COPY SQL.
_UA_EDR_COPY_COLUMNS = (
    "id",
    "generation",
    "subject_kind",
    "record_id",
    "name",
    "name_normalized",
    "short_name",
    "registration_id",
    "legal_form",
    "status",
    "registration_info",
    "termination_info",
    "estate_manager",
    "family_farm",
    "metadata_json",
    "source_resource_id",
    "source_modified_at",
    "raw_reference",
)
_UA_EDR_COPY_SQL = (
    "COPY registry_ua_edr_subjects ("
    + ", ".join(_UA_EDR_COPY_COLUMNS)
    + ") FROM STDIN"
)


class UaEdrRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_sync_state(self) -> UaEdrSyncState | None:
        return self.session.scalar(
            select(UaEdrSyncState).where(
                UaEdrSyncState.source_code == UA_EDR_SOURCE_CODE
            )
        )

    def ensure_sync_state(self) -> UaEdrSyncState:
        state = self.get_sync_state()
        if state is None:
            state = UaEdrSyncState(source_code=UA_EDR_SOURCE_CODE, status="empty")
            self.session.add(state)
            self.session.flush()
        return state

    def active_generation(self) -> str | None:
        state = self.get_sync_state()
        return state.active_generation if state else None

    def active_official_fingerprint(self) -> str | None:
        """Return the official dataset fingerprint represented by the active mirror."""
        generation = self.active_generation()
        if not generation:
            return None
        metadata = self.active_metadata()
        value = str(metadata.get("official_fingerprint") or "").strip()
        return value or generation

    def active_metadata(self) -> dict:
        state = self.get_sync_state()
        if state is None or not state.metadata_json:
            return {}
        try:
            value = json.loads(state.metadata_json)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def begin_sync(
        self,
        *,
        generation: str,
        dataset_id: str,
        dataset_modified_at: str | None,
        uo_resource_id: str,
        fop_resource_id: str,
        metadata: dict,
    ) -> UaEdrSyncState:
        state = self.ensure_sync_state()
        state.pending_generation = generation
        state.status = "loading"
        state.dataset_id = dataset_id
        state.dataset_modified_at = dataset_modified_at
        state.uo_resource_id = uo_resource_id
        state.fop_resource_id = fop_resource_id
        state.uo_record_count = 0
        state.fop_record_count = 0
        state.last_error = None
        state.metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        self.session.flush()
        return state

    def mark_ready(
        self,
        *,
        generation: str,
        uo_count: int,
        fop_count: int,
        metadata: dict,
    ) -> UaEdrSyncState:
        state = self.ensure_sync_state()
        state.active_generation = generation
        state.pending_generation = None
        state.status = "ready"
        state.uo_record_count = int(uo_count)
        state.fop_record_count = int(fop_count)
        state.last_error = None
        state.metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        self.session.flush()
        return state

    def mark_failed(self, *, generation: str, error: str, metadata: dict | None = None) -> None:
        state = self.ensure_sync_state()
        if state.pending_generation == generation:
            state.pending_generation = None
        state.status = "failed"
        state.last_error = (error or "Unknown EDR sync failure")[:8000]
        if metadata is not None:
            state.metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        self.session.flush()

    def supports_postgres_copy(self) -> bool:
        """Return True only for a real PostgreSQL SQLAlchemy bind."""
        bind = self.session.get_bind()
        dialect = getattr(bind, "dialect", None)
        return getattr(dialect, "name", None) == "postgresql"

    def bulk_insert(self, rows: Iterable[dict]) -> int:
        """Portable SQLAlchemy executemany fallback used by tests/non-Postgres DBs."""
        payload = list(rows)
        if not payload:
            return 0
        self.session.execute(insert(UaEdrSubject), payload)
        self.session.flush()
        return len(payload)

    def copy_insert(self, rows: Iterable[dict]) -> int:
        """Load one bounded batch through psycopg COPY FROM STDIN.

        COPY participates in the transaction already owned by ``Session``.
        No commit is performed here. The sync command remains the transaction
        boundary and can keep the old active generation available until the new
        one is complete.
        """
        payload = list(rows)
        if not payload:
            return 0
        if not self.supports_postgres_copy():
            return self.bulk_insert(payload)

        sa_connection = self.session.connection()
        proxied = sa_connection.connection
        driver_connection = getattr(proxied, "driver_connection", proxied)

        with driver_connection.cursor() as cursor:
            with cursor.copy(_UA_EDR_COPY_SQL) as copy:
                for row in payload:
                    copy.write_row(self._copy_row(row))
        return len(payload)

    @staticmethod
    def _copy_row(row: dict) -> tuple:
        return (
            uuid4(),
            row.get("generation"),
            row.get("subject_kind"),
            row.get("record_id"),
            row.get("name"),
            row.get("name_normalized"),
            row.get("short_name"),
            row.get("registration_id"),
            row.get("legal_form"),
            row.get("status"),
            row.get("registration_info"),
            row.get("termination_info"),
            row.get("estate_manager"),
            row.get("family_farm"),
            row.get("metadata_json"),
            row.get("source_resource_id"),
            row.get("source_modified_at"),
            row.get("raw_reference"),
        )

    def delete_generation(self, generation: str) -> int:
        result = self.session.execute(
            delete(UaEdrSubject).where(UaEdrSubject.generation == generation)
        )
        return int(result.rowcount or 0)

    def delete_except_generation(self, generation: str) -> int:
        result = self.session.execute(
            delete(UaEdrSubject).where(UaEdrSubject.generation != generation)
        )
        return int(result.rowcount or 0)

    def search_registration_id(self, value: str, *, limit: int = 20) -> list[UaEdrSubject]:
        generation = self.active_generation()
        identifier = (value or "").strip()
        if not generation or not identifier:
            return []
        statement = (
            select(UaEdrSubject)
            .where(
                UaEdrSubject.generation == generation,
                UaEdrSubject.registration_id == identifier,
            )
            .order_by(UaEdrSubject.subject_kind, UaEdrSubject.name_normalized)
            .limit(max(1, min(int(limit), 100)))
        )
        return list(self.session.scalars(statement).all())

    def search_name(
        self,
        value: str,
        *,
        subject_kind: str | None = None,
        limit: int = 20,
    ) -> list[UaEdrSubject]:
        generation = self.active_generation()
        normalized = normalize_ua_edr_name(value)
        if not generation or not normalized:
            return []
        conditions = [
            UaEdrSubject.generation == generation,
            UaEdrSubject.name_normalized.startswith(normalized, autoescape=True),
        ]
        if subject_kind:
            conditions.append(UaEdrSubject.subject_kind == subject_kind)
        statement = (
            select(UaEdrSubject)
            .where(*conditions)
            .order_by(UaEdrSubject.name_normalized, UaEdrSubject.record_id)
            .limit(max(1, min(int(limit), 100)))
        )
        return list(self.session.scalars(statement).all())
