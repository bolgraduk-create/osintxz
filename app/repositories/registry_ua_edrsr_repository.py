"""Persistence/query boundary for the server-side Ukraine EDRSR mirror."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models.registry_ua_edrsr import UaEdrsrDecision, UaEdrsrSyncState


UA_EDRSR_SOURCE_CODE = "ua_edrsr"

_UA_EDRSR_COPY_COLUMNS = (
    "id",
    "dataset_year",
    "generation",
    "doc_id",
    "court_code",
    "court_name",
    "instance_name",
    "region_name",
    "judgment_code",
    "judgment_name",
    "justice_kind",
    "justice_kind_name",
    "category_code",
    "category_name",
    "cause_num",
    "cause_num_normalized",
    "adjudication_date",
    "receipt_date",
    "judge",
    "doc_url",
    "status",
    "date_publ",
    "source_dataset_id",
    "source_resource_id",
    "source_modified_at",
    "source_hash",
    "raw_reference",
)
_UA_EDRSR_COPY_SQL = (
    "COPY registry_ua_edrsr_decisions ("
    + ", ".join(_UA_EDRSR_COPY_COLUMNS)
    + ") FROM STDIN"
)


def normalize_case_number(value: str | None) -> str:
    """Normalize a case number without changing its legal meaning."""
    normalized = re.sub(r"\s+", "", (value or "").strip())
    return normalized.casefold()


class UaEdrsrRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_sync_state(self, dataset_year: int) -> UaEdrsrSyncState | None:
        return self.session.scalar(
            select(UaEdrsrSyncState).where(
                UaEdrsrSyncState.source_code == UA_EDRSR_SOURCE_CODE,
                UaEdrsrSyncState.dataset_year == int(dataset_year),
            )
        )

    def ensure_sync_state(self, dataset_year: int) -> UaEdrsrSyncState:
        year = int(dataset_year)
        state = self.get_sync_state(year)
        if state is None:
            state = UaEdrsrSyncState(
                source_code=UA_EDRSR_SOURCE_CODE,
                dataset_year=year,
                status="empty",
                record_count=0,
            )
            self.session.add(state)
            self.session.flush()
        return state

    def active_generations(self) -> dict[int, str]:
        rows = self.session.scalars(
            select(UaEdrsrSyncState).where(
                UaEdrsrSyncState.source_code == UA_EDRSR_SOURCE_CODE,
                UaEdrsrSyncState.active_generation.is_not(None),
            )
        ).all()
        return {
            int(row.dataset_year): str(row.active_generation)
            for row in rows
            if row.active_generation
        }

    def ready_states(self) -> list[UaEdrsrSyncState]:
        return list(
            self.session.scalars(
                select(UaEdrsrSyncState)
                .where(
                    UaEdrsrSyncState.source_code == UA_EDRSR_SOURCE_CODE,
                    UaEdrsrSyncState.active_generation.is_not(None),
                )
                .order_by(UaEdrsrSyncState.dataset_year)
            ).all()
        )

    def ready_years(self) -> tuple[int, ...]:
        return tuple(sorted(self.active_generations()))

    def active_metadata(self, dataset_year: int) -> dict:
        state = self.get_sync_state(dataset_year)
        if state is None or not state.metadata_json:
            return {}
        try:
            value = json.loads(state.metadata_json)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def active_official_fingerprint(self, dataset_year: int) -> str | None:
        state = self.get_sync_state(dataset_year)
        if state is None or not state.active_generation:
            return None
        value = str(self.active_metadata(dataset_year).get("official_fingerprint") or "").strip()
        return value or str(state.active_generation)

    def begin_sync(
        self,
        *,
        dataset_year: int,
        generation: str,
        dataset_id: str,
        resource_id: str,
        dataset_modified_at: str | None,
        resource_modified_at: str | None,
        metadata: dict,
    ) -> UaEdrsrSyncState:
        state = self.ensure_sync_state(dataset_year)
        active_metadata = self.active_metadata(dataset_year) if state.active_generation else {}
        state.pending_generation = generation
        state.status = "loading"
        state.dataset_id = dataset_id
        state.resource_id = resource_id
        state.dataset_modified_at = dataset_modified_at
        state.resource_modified_at = resource_modified_at
        if not state.active_generation:
            state.record_count = 0
        state.last_error = None
        merged_metadata = dict(active_metadata)
        merged_metadata["pending_sync"] = dict(metadata)
        state.metadata_json = json.dumps(
            merged_metadata, ensure_ascii=False, sort_keys=True
        )
        self.session.flush()
        return state

    def mark_ready(
        self,
        *,
        dataset_year: int,
        generation: str,
        record_count: int,
        source_hash: str,
        metadata: dict,
    ) -> UaEdrsrSyncState:
        state = self.ensure_sync_state(dataset_year)
        state.active_generation = generation
        state.pending_generation = None
        state.status = "ready"
        state.record_count = int(record_count)
        state.source_hash = source_hash
        state.last_error = None
        state.metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        self.session.flush()
        return state

    def mark_failed(
        self,
        *,
        dataset_year: int,
        generation: str,
        error: str,
        metadata: dict | None = None,
    ) -> None:
        state = self.ensure_sync_state(dataset_year)
        if state.pending_generation == generation:
            state.pending_generation = None
        state.status = "failed"
        state.last_error = (error or "Unknown EDRSR sync failure")[:8000]
        if metadata is not None:
            if state.active_generation:
                merged_metadata = self.active_metadata(dataset_year)
                merged_metadata.pop("pending_sync", None)
                merged_metadata["last_failed_sync"] = dict(metadata)
                merged_metadata["last_failed_error"] = state.last_error
            else:
                merged_metadata = {
                    "failed_sync": dict(metadata),
                    "last_failed_error": state.last_error,
                }
            state.metadata_json = json.dumps(
                merged_metadata, ensure_ascii=False, sort_keys=True
            )
        self.session.flush()

    def supports_postgres_copy(self) -> bool:
        bind = self.session.get_bind()
        dialect = getattr(bind, "dialect", None)
        return getattr(dialect, "name", None) == "postgresql"

    def bulk_insert(self, rows: Iterable[dict]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        self.session.execute(insert(UaEdrsrDecision), payload)
        self.session.flush()
        return len(payload)

    def copy_insert(self, rows: Iterable[dict]) -> int:
        payload = list(rows)
        if not payload:
            return 0
        if not self.supports_postgres_copy():
            return self.bulk_insert(payload)

        sa_connection = self.session.connection()
        proxied = sa_connection.connection
        driver_connection = getattr(proxied, "driver_connection", proxied)
        with driver_connection.cursor() as cursor:
            with cursor.copy(_UA_EDRSR_COPY_SQL) as copy:
                for row in payload:
                    copy.write_row(self._copy_row(row))
        return len(payload)

    @staticmethod
    def _copy_row(row: dict) -> tuple:
        return (
            uuid4(),
            row.get("dataset_year"),
            row.get("generation"),
            row.get("doc_id"),
            row.get("court_code"),
            row.get("court_name"),
            row.get("instance_name"),
            row.get("region_name"),
            row.get("judgment_code"),
            row.get("judgment_name"),
            row.get("justice_kind"),
            row.get("justice_kind_name"),
            row.get("category_code"),
            row.get("category_name"),
            row.get("cause_num"),
            row.get("cause_num_normalized"),
            row.get("adjudication_date"),
            row.get("receipt_date"),
            row.get("judge"),
            row.get("doc_url"),
            row.get("status"),
            row.get("date_publ"),
            row.get("source_dataset_id"),
            row.get("source_resource_id"),
            row.get("source_modified_at"),
            row.get("source_hash"),
            row.get("raw_reference"),
        )

    def delete_generation(self, dataset_year: int, generation: str) -> int:
        result = self.session.execute(
            delete(UaEdrsrDecision).where(
                UaEdrsrDecision.dataset_year == int(dataset_year),
                UaEdrsrDecision.generation == generation,
            )
        )
        return int(result.rowcount or 0)

    def delete_old_generations(self, dataset_year: int, keep_generation: str) -> int:
        result = self.session.execute(
            delete(UaEdrsrDecision).where(
                UaEdrsrDecision.dataset_year == int(dataset_year),
                UaEdrsrDecision.generation != keep_generation,
            )
        )
        return int(result.rowcount or 0)

    def search_case_number(
        self,
        value: str,
        *,
        limit: int = 20,
        dataset_year: int | None = None,
    ) -> list[UaEdrsrDecision]:
        normalized = normalize_case_number(value)
        if not normalized:
            return []

        active = self.active_generations()
        if dataset_year is not None:
            year = int(dataset_year)
            generation = active.get(year)
            if not generation:
                return []
            active_pairs = ((year, generation),)
        else:
            active_pairs = tuple(active.items())

        if not active_pairs:
            return []

        from sqlalchemy import and_, or_

        generation_filter = or_(
            *(
                and_(
                    UaEdrsrDecision.dataset_year == year,
                    UaEdrsrDecision.generation == generation,
                )
                for year, generation in active_pairs
            )
        )
        statement = (
            select(UaEdrsrDecision)
            .where(
                generation_filter,
                UaEdrsrDecision.cause_num_normalized == normalized,
            )
            .order_by(
                UaEdrsrDecision.adjudication_date.desc().nullslast(),
                UaEdrsrDecision.doc_id.desc(),
            )
            .limit(max(1, min(int(limit), 100)))
        )
        return list(self.session.scalars(statement).all())
