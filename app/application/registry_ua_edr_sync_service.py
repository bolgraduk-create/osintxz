"""Server-side workflow for building a new Ukraine EDR mirror generation.

The desktop application never runs this workflow. Registry Backend ingestion
owns it. The service itself never commits: the command/background-job boundary
owns bounded transactions while the previous active generation remains usable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import zipfile

from app.infrastructure.registries.ukraine_edr_downloader import (
    UaEdrDatasetClient,
    UaEdrDatasetResources,
    UaEdrResource,
)
from app.infrastructure.registries.ukraine_edr_parser import UaEdrXmlParser
from app.repositories.registry_ua_edr_repository import UaEdrRepository


@dataclass(frozen=True, slots=True)
class UaEdrSyncPlan:
    resources: UaEdrDatasetResources
    generation: str
    unchanged: bool


@dataclass(frozen=True, slots=True)
class UaEdrImportProgress:
    subject_kind: str
    imported: int
    batch_size: int
    write_mode: str = "sqlalchemy"


class UaEdrSyncService:
    WRITE_MODES = frozenset({"auto", "copy", "sqlalchemy"})

    def __init__(
        self,
        *,
        repository: UaEdrRepository,
        dataset_client: UaEdrDatasetClient | None = None,
        parser: UaEdrXmlParser | None = None,
    ) -> None:
        self.repository = repository
        self.dataset_client = dataset_client or UaEdrDatasetClient()
        self.parser = parser or UaEdrXmlParser()

    def build_plan(self, *, timeout: int = 30) -> UaEdrSyncPlan:
        resources = self.dataset_client.resolve_latest(timeout=timeout)
        generation = resources.fingerprint
        return UaEdrSyncPlan(
            resources=resources,
            generation=generation,
            unchanged=(
                self.repository.active_official_fingerprint() == generation
            ),
        )

    def begin(self, plan: UaEdrSyncPlan) -> None:
        # Remove only a stale/incomplete copy of the generation we are about to
        # rebuild. The currently active generation is never deleted here.
        if self.repository.active_generation() != plan.generation:
            self.repository.delete_generation(plan.generation)
        self.repository.begin_sync(
            generation=plan.generation,
            dataset_id=plan.resources.dataset_id,
            dataset_modified_at=plan.resources.modified_at,
            uo_resource_id=plan.resources.uo.resource_id,
            fop_resource_id=plan.resources.fop.resource_id,
            metadata=self._state_metadata(plan),
        )

    def resolve_write_mode(self, requested: str = "auto") -> str:
        mode = str(requested or "auto").strip().casefold()
        if mode not in self.WRITE_MODES:
            raise ValueError(
                "write_mode must be one of: auto, copy, sqlalchemy"
            )
        if mode == "auto":
            return (
                "copy"
                if self.repository.supports_postgres_copy()
                else "sqlalchemy"
            )
        if mode == "copy" and not self.repository.supports_postgres_copy():
            raise RuntimeError(
                "PostgreSQL COPY ingestion was requested but the current "
                "database bind is not PostgreSQL."
            )
        return mode

    def iter_import_zip_batches(
        self,
        *,
        archive_path: Path,
        subject_kind: str,
        generation: str,
        resource: UaEdrResource,
        batch_size: int = 50_000,
        max_records: int | None = None,
        max_uncompressed_bytes: int = 12 * 1024 * 1024 * 1024,
        write_mode: str = "auto",
    ):
        batch_size = max(1, int(batch_size))
        resolved_write_mode = self.resolve_write_mode(write_mode)
        imported = 0
        batch: list[dict] = []

        with zipfile.ZipFile(archive_path) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            if len(members) > 16:
                raise ValueError("EDR archive contains too many members.")
            total_uncompressed = sum(int(m.file_size) for m in members)
            if total_uncompressed > max_uncompressed_bytes:
                raise ValueError("EDR archive exceeds configured uncompressed size limit.")
            xml_members = [m for m in members if m.filename.casefold().endswith(".xml")]
            if len(xml_members) != 1:
                raise ValueError("EDR archive must contain exactly one XML payload.")
            member = xml_members[0]
            normalized_name = member.filename.replace("\\", "/")
            if normalized_name.startswith("/") or "../" in f"/{normalized_name}":
                raise ValueError("Unsafe EDR ZIP member path.")

            with archive.open(member, "r") as stream:
                for parsed in self.parser.iter_subjects(stream, subject_kind=subject_kind):
                    batch.append(
                        parsed.to_row(
                            generation=generation,
                            source_resource_id=resource.resource_id,
                            source_modified_at=resource.modified_at,
                        )
                    )
                    imported += 1
                    if len(batch) >= batch_size:
                        self._write_batch(batch, resolved_write_mode)
                        yield UaEdrImportProgress(
                            subject_kind,
                            imported,
                            len(batch),
                            resolved_write_mode,
                        )
                        batch = []
                    if max_records is not None and imported >= max_records:
                        break

        if batch:
            self._write_batch(batch, resolved_write_mode)
            yield UaEdrImportProgress(
                subject_kind,
                imported,
                len(batch),
                resolved_write_mode,
            )

    def _write_batch(self, batch: list[dict], write_mode: str) -> int:
        if write_mode == "copy":
            return self.repository.copy_insert(batch)
        return self.repository.bulk_insert(batch)

    def mark_ready(self, plan: UaEdrSyncPlan, *, uo_count: int, fop_count: int) -> None:
        metadata = self._state_metadata(plan)
        metadata.update({"uo_record_count": int(uo_count), "fop_record_count": int(fop_count)})
        self.repository.mark_ready(
            generation=plan.generation,
            uo_count=uo_count,
            fop_count=fop_count,
            metadata=metadata,
        )

    def mark_failed(self, plan: UaEdrSyncPlan, error: Exception | str) -> None:
        self.repository.mark_failed(
            generation=plan.generation,
            error=str(error),
            metadata=self._state_metadata(plan),
        )

    def cleanup_old_generations(self, active_generation: str) -> int:
        return self.repository.delete_except_generation(active_generation)

    @staticmethod
    def _state_metadata(plan: UaEdrSyncPlan) -> dict:
        return {
            "source": "data.gov.ua",
            "dataset_id": plan.resources.dataset_id,
            "dataset_modified_at": plan.resources.modified_at,
            "generation": plan.generation,
            "official_fingerprint": plan.resources.fingerprint,
            "uo": {
                "resource_id": plan.resources.uo.resource_id,
                "modified_at": plan.resources.uo.modified_at,
                "hash": plan.resources.uo.hash_value,
            },
            "fop": {
                "resource_id": plan.resources.fop.resource_id,
                "modified_at": plan.resources.fop.modified_at,
                "hash": plan.resources.fop.hash_value,
            },
        }
