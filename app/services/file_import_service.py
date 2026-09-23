"""
File import service.

Safely imports external files into an investigation.

Responsible for:

- validating source paths
- detecting file and evidence types
- calculating SHA256
- preventing duplicate imports inside one case
- copying original files into managed storage
- creating Source and Evidence records
- storing basic technical metadata
- cleaning up copied files when an import fails

Does NOT:

- commit or roll back database transactions
- process OCR
- transcribe audio
- analyze media with AI
- generate thumbnails
- access desktop widgets
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil

from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from uuid import uuid4

from app.core.config import (
    DOCUMENTS_DIR,
    MEDIA_DIR,
)

from app.models.evidence import (
    Evidence,
    EvidenceType,
)

from app.models.source import (
    Source,
    SourceStatus,
    SourceType,
)

from app.services.collection_service import (
    CollectionService,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.processing.file_processing_router import (
    FileProcessingRouter,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)

from app.security.untrusted_file_policy import (
    UntrustedFilePolicy,
)


class FileImportService:
    """
    Imports one or multiple files into a case.

    The service copies originals into application-managed storage
    and creates one Source plus one Evidence object per file.
    """

    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".gif",
        ".heic",
        ".heif",
    }

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mkv",
        ".mov",
        ".avi",
        ".webm",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".wmv",
    }

    AUDIO_EXTENSIONS = {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".oga",
        ".flac",
        ".opus",
        ".wma",
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf",
        ".txt",
        ".md",
        ".rtf",
        ".doc",
        ".docx",
        ".odt",
        ".xls",
        ".xlsx",
        ".ods",
        ".ppt",
        ".pptx",
        ".odp",
        ".csv",
        ".json",
        ".xml",
        ".html",
        ".htm",
        ".eml",
    }

    ARCHIVE_EXTENSIONS = {
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
    }

    def __init__(
        self,
        collection_service: CollectionService,
        evidence_service: EvidenceService,
        file_processing_router: FileProcessingRouter | None = None,
        *,
        search_indexing_service: (
            SearchIndexingService
            | None
        ) = None,
        media_directory: Path = MEDIA_DIR,
        documents_directory: Path = DOCUMENTS_DIR,
        maximum_file_size_bytes: int | None = None,
        file_security_policy: UntrustedFilePolicy | None = None,
    ) -> None:

        if not isinstance(
            collection_service,
            CollectionService,
        ):

            raise TypeError(
                "collection_service must be a CollectionService."
            )

        if not isinstance(
            evidence_service,
            EvidenceService,
        ):

            raise TypeError(
                "evidence_service must be an EvidenceService."
            )

        self.collection_service = (
            collection_service
        )

        self.evidence_service = (
            evidence_service
        )

        self.file_processing_router = (
            file_processing_router
            or FileProcessingRouter()
        )

        self.search_indexing_service = (
            search_indexing_service
        )

        self.media_directory = Path(
            media_directory
        ).resolve()

        self.documents_directory = Path(
            documents_directory
        ).resolve()

        self.file_security_policy = (
            file_security_policy
            or UntrustedFilePolicy()
        )

        if maximum_file_size_bytes is None:

            self.maximum_file_size_bytes = None

        else:

            normalized_limit = int(
                maximum_file_size_bytes
            )

            if normalized_limit <= 0:

                raise ValueError(
                    "maximum_file_size_bytes "
                    "must be greater than zero."
                )

            self.maximum_file_size_bytes = (
                normalized_limit
            )

        self.media_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.documents_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ==========================================================
    # Public import API
    # ==========================================================

    def import_file(
        self,
        *,
        case_id: str | UUID,
        file_path: str | Path,
    ) -> dict[str, Any]:
        """
        Import one external file.

        Database commit is intentionally controlled by the caller.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        source_path = self._validate_source_path(
            file_path
        )

        size_bytes = source_path.stat().st_size

        self._validate_file_size(
            size_bytes
        )

        sha256 = self._calculate_sha256(
            source_path
        )

        existing_evidence = (
            self.evidence_service
            .find_case_evidence_by_hash(
                case_id=case_uuid,
                sha256=sha256,
            )
        )

        if existing_evidence is not None:

            return {
                "status": "duplicate",
                "created": False,
                "duplicate": True,
                "source_path": str(
                    source_path
                ),
                "sha256": sha256,
                "processing": {
                    "status": "skipped",
                    "reason": "duplicate",
                    "processor": None,
                    "category": None,
                    "metadata": {},
                    "errors": [],
                },
                "evidence": (
                    self._serialize_evidence(
                        existing_evidence
                    )
                ),
            }

        source_type, evidence_type = (
            self._detect_types(
                source_path
            )
        )

        mime_type = self._detect_mime_type(
            source_path
        )

        storage_root = self._select_storage_root(
            evidence_type
        )

        destination_path = (
            self._build_destination_path(
                storage_root=storage_root,
                case_id=case_uuid,
                source_path=source_path,
            )
        )

        destination_path = (
            self.file_security_policy
            .validate_managed_destination(
                storage_root=storage_root,
                destination_path=destination_path,
            )
        )

        archive_security = None

        if evidence_type == EvidenceType.ARCHIVE:
            archive_security = (
                self.file_security_policy
                .inspect_archive(
                    source_path
                )
            )

        copied = False

        try:

            self._copy_original(
                source_path=source_path,
                destination_path=destination_path,
            )

            copied = True

            imported_at = datetime.now(
                UTC
            ).isoformat()

            processing_result = (
                self.file_processing_router
                .process(
                    destination_path
                )
            )

            if archive_security is not None:
                processing_result = {
                    **processing_result,
                    "metadata": {
                        **dict(
                            processing_result.get(
                                "metadata",
                                {},
                            )
                            or {}
                        ),
                        "security": archive_security,
                    },
                }

            source_metadata = {
                "import_kind": "file",
                "original_name": (
                    source_path.name
                ),
                "original_suffix": (
                    source_path.suffix.lower()
                ),
                "stored_name": (
                    destination_path.name
                ),
                "stored_path": str(
                    destination_path
                ),
                "mime_type": mime_type,
                "sha256": sha256,
                "size_bytes": size_bytes,
                "imported_at": imported_at,
                "processing": (
                    processing_result
                ),
            }

            source = (
                self.collection_service
                .create_source(
                    case_id=case_uuid,
                    name=source_path.name,
                    source_type=source_type,
                    path=source_path,
                    description=(
                        "Original file imported into "
                        "managed investigation storage."
                    ),
                )
            )

            self._complete_source_record(
                source=source,
                checksum=sha256,
                size_bytes=size_bytes,
                metadata=source_metadata,
            )

            evidence_metadata = {
                **source_metadata,
                "source_id": str(
                    source.id
                ),
                "processing_status": (
                    processing_result.get(
                        "status",
                        "failed",
                    )
                ),
                "processor": (
                    processing_result.get(
                        "processor"
                    )
                ),
                "category": (
                    processing_result.get(
                        "category"
                    )
                ),
                "processing_metadata": (
                    processing_result.get(
                        "metadata",
                        {},
                    )
                ),
                "processing_errors": (
                    processing_result.get(
                        "errors",
                        [],
                    )
                ),
                "derived_artifacts": [],
            }

            evidence = (
                self.collection_service
                .create_evidence(
                    case_id=case_uuid,
                    source_id=source.id,
                    evidence_type=evidence_type,
                    title=source_path.name,
                    value=None,
                    file_path=str(
                        destination_path
                    ),
                    mime_type=mime_type,
                    description=(
                        "Imported file evidence.\n\n"
                        f"Original name: {source_path.name}\n"
                        f"Original path: {source_path}\n"
                        f"Stored path: {destination_path}\n"
                        f"Size: {size_bytes} bytes\n"
                        f"SHA256: {sha256}"
                    ),
                )
            )

            self._complete_evidence_record(
                evidence=evidence,
                sha256=sha256,
                metadata=evidence_metadata,
            )

            return {
                "status": "imported",
                "created": True,
                "duplicate": False,
                "source_path": str(
                    source_path
                ),
                "stored_path": str(
                    destination_path
                ),
                "sha256": sha256,
                "source": (
                    self._serialize_source(
                        source
                    )
                ),
                "evidence": (
                    self._serialize_evidence(
                        evidence
                    )
                ),
            }

        except Exception:

            if (
                copied
                and destination_path.exists()
            ):

                try:

                    destination_path.unlink()

                except OSError:

                    pass

            raise

    def import_files(
        self,
        *,
        case_id: str | UUID,
        file_paths: list[str | Path],
    ) -> dict[str, Any]:
        """
        Import multiple files.

        An error in one file is recorded and does not stop
        processing of the remaining paths.

        Lightweight textual search indexes are created during
        individual imports.

        After all files have been processed, the complete case
        search index is synchronized once and missing semantic
        embeddings are generated.

        The caller still controls the final database transaction.
        """

        if not isinstance(
            file_paths,
            list,
        ):

            raise TypeError(
                "file_paths must be a list."
            )

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        results: list[
            dict[str, Any]
        ] = []

        imported_count = 0
        duplicate_count = 0
        failed_count = 0

        # ------------------------------------------------------
        # Import files
        # ------------------------------------------------------

        for file_path in file_paths:

            try:

                result = self.import_file(
                    case_id=case_uuid,
                    file_path=file_path,
                )

                results.append(
                    result
                )

                if result.get(
                    "duplicate",
                    False,
                ):

                    duplicate_count += 1

                elif result.get(
                    "created",
                    False,
                ):

                    imported_count += 1

            except Exception as error:

                failed_count += 1

                results.append(
                    {
                        "status": "failed",
                        "created": False,
                        "duplicate": False,
                        "source_path": str(
                            file_path
                        ),
                        "error": str(
                            error
                        ),
                    }
                )

        # ------------------------------------------------------
        # Final search synchronization
        # ------------------------------------------------------

        search_statistics = None

        if (
            self.search_indexing_service
            is not None
            and imported_count > 0
        ):

            try:

                search_statistics = (
                    self.search_indexing_service
                    .index_case(
                        case_uuid
                    )
                )

            except Exception as error:

                # File import itself remains successful even if
                # semantic indexing is temporarily unavailable.
                #
                # Search indexing can be retried separately later.

                search_statistics = error

        # ------------------------------------------------------
        # Search result serialization
        # ------------------------------------------------------

        search_result: dict[
            str,
            Any,
        ] = {
            "requested": (
                search_statistics
                is not None
            ),
            "successful": None,
            "error": None,
        }

        if isinstance(
            search_statistics,
            Exception,
        ):

            search_result[
                "successful"
            ] = False

            search_result[
                "error"
            ] = str(
                search_statistics
            )

        elif search_statistics is not None:

            search_result[
                "successful"
            ] = (
                search_statistics.successful
            )

            search_result[
                "search_indexes"
            ] = {
                "processed": (
                    search_statistics
                    .search_indexes
                    .processed
                ),
                "created": (
                    search_statistics
                    .search_indexes
                    .created
                ),
                "updated": (
                    search_statistics
                    .search_indexes
                    .updated
                ),
                "skipped": (
                    search_statistics
                    .search_indexes
                    .skipped
                ),
                "failed": (
                    search_statistics
                    .search_indexes
                    .failed
                ),
            }

            search_result[
                "embeddings"
            ] = {
                "processed": (
                    search_statistics
                    .embeddings
                    .processed
                ),
                "created_or_updated": (
                    search_statistics
                    .embeddings
                    .created_or_updated
                ),
                "skipped": (
                    search_statistics
                    .embeddings
                    .skipped
                ),
                "failed": (
                    search_statistics
                    .embeddings
                    .failed
                ),
            }

        # ------------------------------------------------------
        # Result
        # ------------------------------------------------------

        return {
            "requested": len(
                file_paths
            ),
            "imported": imported_count,
            "duplicates": duplicate_count,
            "failed": failed_count,
            "results": results,
            "search_indexing": (
                search_result
            ),
        }

        # ==========================================================
        # Type detection
        # ==========================================================

        def _detect_types(
            self,
            path: Path,
        ) -> tuple[
            SourceType,
            EvidenceType,
        ]:
            """
            Detect SourceType and EvidenceType from the file extension.
            """

            suffix = path.suffix.lower()

            if suffix in self.IMAGE_EXTENSIONS:

                return (
                    SourceType.IMAGE,
                    EvidenceType.IMAGE,
                )

            if suffix in self.VIDEO_EXTENSIONS:

                return (
                    SourceType.VIDEO,
                    EvidenceType.VIDEO,
                )

            if suffix in self.AUDIO_EXTENSIONS:

                return (
                    SourceType.AUDIO,
                    EvidenceType.AUDIO,
                )

            if suffix == ".pdf":

                return (
                    SourceType.PDF,
                    EvidenceType.DOCUMENT,
                )

            if suffix == ".csv":

                return (
                    SourceType.CSV,
                    EvidenceType.DOCUMENT,
                )

            if suffix == ".json":

                return (
                    SourceType.JSON,
                    EvidenceType.DOCUMENT,
                )

            if suffix in {
                ".html",
                ".htm",
            }:

                return (
                    SourceType.HTML,
                    EvidenceType.DOCUMENT,
                )

            if suffix in self.DOCUMENT_EXTENSIONS:

                return (
                    SourceType.DOCUMENT,
                    EvidenceType.DOCUMENT,
                )

            if suffix in self.ARCHIVE_EXTENSIONS:

                return (
                    SourceType.FILE,
                    EvidenceType.ARCHIVE,
                )

            return (
                SourceType.FILE,
                EvidenceType.OTHER,
            )

    @staticmethod
    def _detect_mime_type(
        path: Path,
    ) -> str:
        """
        Detect MIME type without reading executable content.
        """

        mime_type, _ = mimetypes.guess_type(
            path.name
        )

        return (
            mime_type
            or "application/octet-stream"
        )

    def _select_storage_root(
        self,
        evidence_type: EvidenceType,
    ) -> Path:
        """
        Select managed storage directory for the evidence type.
        """

        if evidence_type in {
            EvidenceType.IMAGE,
            EvidenceType.VIDEO,
            EvidenceType.AUDIO,
        }:

            return self.media_directory

        return self.documents_directory

    # ==========================================================
    # File operations
    # ==========================================================

    @staticmethod
    def _calculate_sha256(
        path: Path,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> str:
        """
        Calculate SHA256 without loading the complete file into RAM.
        """

        digest = hashlib.sha256()

        with path.open(
            "rb"
        ) as source_file:

            while True:

                chunk = source_file.read(
                    chunk_size
                )

                if not chunk:

                    break

                digest.update(
                    chunk
                )

        return digest.hexdigest()

    @staticmethod
    def _copy_original(
        *,
        source_path: Path,
        destination_path: Path,
    ) -> None:
        """
        Copy an original file while preserving basic timestamps.
        """

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source_path,
            destination_path,
        )

    @staticmethod
    def _build_destination_path(
        *,
        storage_root: Path,
        case_id: UUID,
        source_path: Path,
    ) -> Path:
        """
        Build a collision-resistant managed path.
        """

        case_directory = (
            storage_root
            / str(
                case_id
            )
            / "originals"
        )

        case_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_stem = (
            FileImportService
            ._sanitize_filename_part(
                source_path.stem
            )
        )

        suffix = source_path.suffix.lower()

        unique_name = (
            f"{safe_stem}_"
            f"{uuid4().hex}"
            f"{suffix}"
        )

        return (
            case_directory
            / unique_name
        ).resolve()

    @staticmethod
    def _sanitize_filename_part(
        value: str,
    ) -> str:
        """
        Convert a filename stem to a safe portable name.
        """

        normalized = "".join(
            character
            if (
                character.isalnum()
                or character in {
                    "-",
                    "_",
                }
            )
            else "_"
            for character in str(
                value
                or ""
            )
        )

        normalized = (
            normalized
            .strip(
                "._-"
            )
        )

        if not normalized:

            return "file"

        return normalized[
            :100
        ]

    # ==========================================================
    # ORM completion
    # ==========================================================

    @staticmethod
    def _complete_source_record(
        *,
        source: Source,
        checksum: str,
        size_bytes: int,
        metadata: dict[str, Any],
    ) -> None:
        """
        Fill technical Source fields after creation.
        """

        source.checksum = checksum
        source.size_bytes = size_bytes
        source.imported_records = 1
        source.status = SourceStatus.IMPORTED
        source.metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _complete_evidence_record(
        *,
        evidence: Evidence,
        sha256: str,
        metadata: dict[str, Any],
    ) -> None:
        """
        Fill technical Evidence fields after creation.
        """

        evidence.sha256 = sha256
        evidence.metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_source_path(
        self,
        file_path: str | Path,
    ) -> Path:
        """
        Validate an external source file through the shared security policy.
        """

        return (
            self.file_security_policy
            .validate_source_path(
                file_path
            )
        )

    def _validate_file_size(
        self,
        size_bytes: int,
    ) -> None:
        """
        Validate configured file-size limit.
        """

        self.file_security_policy.validate_file_size(
            size_bytes
        )

        if (
            self.maximum_file_size_bytes
            is not None
            and size_bytes
            > self.maximum_file_size_bytes
        ):

            raise ValueError(
                "File exceeds the configured size limit: "
                f"{size_bytes} bytes."
            )

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Convert an identifier to UUID.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain a valid UUID."
            ) from error

    # ==========================================================
    # Serialization
    # ==========================================================

    @staticmethod
    def _serialize_source(
        source: Source,
    ) -> dict[str, Any]:
        """
        Serialize imported Source information.
        """

        return {
            "id": str(
                source.id
            ),
            "case_id": str(
                source.case_id
            ),
            "name": source.name,
            "type": (
                source.source_type.value
            ),
            "status": (
                source.status.value
            ),
            "original_path": (
                source.original_path
            ),
            "checksum": (
                source.checksum
            ),
            "size_bytes": (
                source.size_bytes
            ),
        }

    @staticmethod
    def _serialize_evidence(
        evidence: Evidence,
    ) -> dict[str, Any]:
        """
        Serialize imported Evidence information.
        """

        return {
            "id": str(
                evidence.id
            ),
            "case_id": str(
                evidence.case_id
            ),
            "source_id": str(
                evidence.source_id
            ),
            "title": evidence.title,
            "type": (
                evidence.evidence_type.value
            ),
            "file_path": (
                evidence.file_path
            ),
            "mime_type": (
                evidence.mime_type
            ),
            "sha256": (
                evidence.sha256
            ),
        }