"""Server-side yearly synchronization for Ukraine EDRSR.

The previous active generation for a year remains queryable until the new
archive has been parsed, loaded and explicitly activated. The service never
commits; the command/background-job boundary owns transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import zipfile

from app.infrastructure.registries.ukraine_edrsr_downloader import (
    UaEdrsrDatasetClient,
    UaEdrsrDatasetResources,
)
from app.infrastructure.registries.ukraine_edrsr_parser import (
    DOCUMENTS_FILENAME,
    REFERENCE_FILENAMES,
    UaEdrsrReferenceData,
    iter_documents,
    parse_reference_file,
)
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


@dataclass(frozen=True, slots=True)
class UaEdrsrSyncPlan:
    dataset_year: int
    resources: UaEdrsrDatasetResources
    generation: str
    unchanged: bool


@dataclass(frozen=True, slots=True)
class UaEdrsrImportProgress:
    dataset_year: int
    imported: int
    batch_size: int
    write_mode: str = "sqlalchemy"


class UaEdrsrSyncService:
    WRITE_MODES = frozenset({"auto", "copy", "sqlalchemy"})
    MAX_ARCHIVE_UNCOMPRESSED_BYTES = 32 * 1024 * 1024 * 1024

    def __init__(
        self,
        *,
        repository: UaEdrsrRepository,
        dataset_client: UaEdrsrDatasetClient | None = None,
    ) -> None:
        self.repository = repository
        self.dataset_client = dataset_client or UaEdrsrDatasetClient()

    def build_plan(self, *, dataset_year: int) -> UaEdrsrSyncPlan:
        resources = self.dataset_client.resolve_year(dataset_year)
        fingerprint = resources.fingerprint
        return UaEdrsrSyncPlan(
            dataset_year=int(resources.dataset_year),
            resources=resources,
            generation=fingerprint,
            unchanged=(
                self.repository.active_official_fingerprint(resources.dataset_year)
                == fingerprint
            ),
        )

    def resolve_write_mode(self, write_mode: str) -> str:
        normalized = (write_mode or "auto").strip().casefold()
        if normalized not in self.WRITE_MODES:
            raise ValueError(f"Unsupported EDRSR write mode: {write_mode}")
        if normalized == "auto":
            return "copy" if self.repository.supports_postgres_copy() else "sqlalchemy"
        if normalized == "copy" and not self.repository.supports_postgres_copy():
            raise RuntimeError(
                "PostgreSQL COPY ingestion was requested but the current "
                "database bind is not PostgreSQL."
            )
        return normalized

    def begin(self, plan: UaEdrsrSyncPlan) -> None:
        self.repository.delete_generation(plan.dataset_year, plan.generation)
        self.repository.begin_sync(
            dataset_year=plan.dataset_year,
            generation=plan.generation,
            dataset_id=plan.resources.dataset_id,
            resource_id=plan.resources.resource.resource_id,
            dataset_modified_at=plan.resources.modified_at,
            resource_modified_at=plan.resources.resource.modified_at,
            metadata=self._metadata(plan),
        )

    def iter_import_zip_batches(
        self,
        *,
        archive_path: Path,
        plan: UaEdrsrSyncPlan,
        source_hash: str,
        batch_size: int = 50_000,
        write_mode: str = "auto",
    ):
        size = int(batch_size)
        if size < 1:
            raise ValueError("EDRSR batch_size must be at least 1.")
        resolved_mode = self.resolve_write_mode(write_mode)
        imported = 0

        with zipfile.ZipFile(Path(archive_path), "r") as archive:
            members = self._validate_archive(archive)
            references = self._load_references(archive, members)
            documents_member = members[DOCUMENTS_FILENAME]

            batch: list[dict] = []
            with archive.open(documents_member, "r") as documents:
                for row in iter_documents(
                    documents,
                    dataset_year=plan.dataset_year,
                    generation=plan.generation,
                    references=references,
                    source_dataset_id=plan.resources.dataset_id,
                    source_resource_id=plan.resources.resource.resource_id,
                    source_modified_at=plan.resources.resource.modified_at,
                    source_hash=source_hash,
                ):
                    batch.append(row)
                    if len(batch) >= size:
                        imported += self._write_batch(batch, resolved_mode)
                        yield UaEdrsrImportProgress(
                            dataset_year=plan.dataset_year,
                            imported=imported,
                            batch_size=len(batch),
                            write_mode=resolved_mode,
                        )
                        batch = []

            if batch:
                imported += self._write_batch(batch, resolved_mode)
                yield UaEdrsrImportProgress(
                    dataset_year=plan.dataset_year,
                    imported=imported,
                    batch_size=len(batch),
                    write_mode=resolved_mode,
                )

    def mark_ready(
        self,
        plan: UaEdrsrSyncPlan,
        *,
        record_count: int,
        source_hash: str,
    ) -> None:
        metadata = self._metadata(plan)
        metadata["download_sha256"] = source_hash
        self.repository.mark_ready(
            dataset_year=plan.dataset_year,
            generation=plan.generation,
            record_count=record_count,
            source_hash=source_hash,
            metadata=metadata,
        )

    def mark_failed(self, plan: UaEdrsrSyncPlan, error: object) -> None:
        self.repository.mark_failed(
            dataset_year=plan.dataset_year,
            generation=plan.generation,
            error=str(error),
            metadata=self._metadata(plan),
        )

    def cleanup_old_generations(self, plan: UaEdrsrSyncPlan) -> int:
        return self.repository.delete_old_generations(
            plan.dataset_year,
            plan.generation,
        )

    def _write_batch(self, rows: list[dict], write_mode: str) -> int:
        if write_mode == "copy":
            return self.repository.copy_insert(rows)
        return self.repository.bulk_insert(rows)

    def _validate_archive(self, archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
        members: dict[str, zipfile.ZipInfo] = {}
        total_uncompressed = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise ValueError("Encrypted files are not allowed in EDRSR archives.")
            total_uncompressed += int(info.file_size or 0)
            if total_uncompressed > self.MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError("EDRSR archive exceeds configured uncompressed size limit.")
            basename = PurePosixPath(info.filename.replace("\\", "/")).name.casefold()
            if basename in members:
                raise ValueError(f"Duplicate EDRSR archive member: {basename}")
            if basename == DOCUMENTS_FILENAME or basename in REFERENCE_FILENAMES:
                members[basename] = info

        if DOCUMENTS_FILENAME not in members:
            raise ValueError("EDRSR archive does not contain documents.csv.")
        return members

    @staticmethod
    def _load_references(
        archive: zipfile.ZipFile,
        members: dict[str, zipfile.ZipInfo],
    ) -> UaEdrsrReferenceData:
        values: dict[str, dict] = {}
        for filename in sorted(REFERENCE_FILENAMES):
            member = members.get(filename)
            if member is None:
                values[filename] = {}
                continue
            with archive.open(member, "r") as stream:
                values[filename] = parse_reference_file(filename, stream)

        return UaEdrsrReferenceData(
            categories=values["cause_categories.csv"],
            courts=values["courts.csv"],
            instances=values["instances.csv"],
            judgments=values["judgment_forms.csv"],
            justice_kinds=values["justice_kinds.csv"],
            regions=values["regions.csv"],
        )

    @staticmethod
    def _metadata(plan: UaEdrsrSyncPlan) -> dict:
        resource = plan.resources.resource
        return {
            "official_fingerprint": plan.resources.fingerprint,
            "dataset_year": plan.dataset_year,
            "dataset_id": plan.resources.dataset_id,
            "dataset_name": plan.resources.dataset_name,
            "dataset_modified_at": plan.resources.modified_at,
            "dataset_page": plan.resources.dataset_page,
            "resource_id": resource.resource_id,
            "resource_name": resource.name,
            "resource_modified_at": resource.modified_at,
            "official_resource_hash": resource.hash_value,
            "source": "data.gov.ua",
            "public_data_only": True,
        }
