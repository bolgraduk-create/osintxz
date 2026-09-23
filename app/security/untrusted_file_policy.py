"""Security boundaries for untrusted local files and archives.

R14.2c keeps imported originals intact and treats archives as evidence, not as
implicit extraction requests. ZIP/TAR-like containers receive a metadata
preflight before they are copied into managed storage.

No method in this module extracts an archive member to disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from typing import Any
import zipfile


class UntrustedFilePolicyError(ValueError):
    """Raised when an untrusted file violates an import security boundary."""


@dataclass(frozen=True, slots=True)
class UntrustedFilePolicy:
    """Conservative limits for desktop file import and archive inspection."""

    max_file_size_bytes: int = 4 * 1024 * 1024 * 1024
    max_archive_members: int = 10_000
    max_archive_member_size_bytes: int = 512 * 1024 * 1024
    max_archive_total_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_archive_compression_ratio: float = 250.0
    max_archive_path_depth: int = 32
    max_nested_archive_candidates: int = 100

    _ARCHIVE_SUFFIXES = frozenset(
        {
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".tgz",
            ".tbz",
            ".tbz2",
            ".txz",
        }
    )

    def validate_source_path(
        self,
        file_path: str | Path,
    ) -> Path:
        """Resolve one external file without following user-selected symlinks."""

        raw = Path(file_path).expanduser()

        try:
            if raw.is_symlink():
                raise UntrustedFilePolicyError(
                    "Symbolic-link imports are blocked by the file security policy."
                )
        except OSError as exc:
            raise UntrustedFilePolicyError(
                "Unable to inspect the source path."
            ) from exc

        try:
            path = raw.resolve(strict=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"File does not exist: {raw}"
            ) from exc
        except OSError as exc:
            raise UntrustedFilePolicyError(
                "Source path cannot be resolved safely."
            ) from exc

        if not path.is_file():
            raise UntrustedFilePolicyError(
                f"Path is not a regular file: {path}"
            )

        self.validate_file_size(path.stat().st_size)

        return path

    def validate_file_size(
        self,
        size_bytes: int,
    ) -> None:
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
            raise UntrustedFilePolicyError(
                "File size must be an integer."
            )

        if size_bytes < 0:
            raise UntrustedFilePolicyError(
                "Invalid file size."
            )

        if size_bytes > self.max_file_size_bytes:
            raise UntrustedFilePolicyError(
                "File exceeds the import security size limit: "
                f"{size_bytes} bytes."
            )

    def validate_managed_destination(
        self,
        *,
        storage_root: str | Path,
        destination_path: str | Path,
    ) -> Path:
        """Ensure a generated destination cannot escape its managed root."""

        root = Path(storage_root).expanduser().resolve(strict=False)
        destination = Path(destination_path).expanduser().resolve(strict=False)

        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise UntrustedFilePolicyError(
                "Managed destination escapes the configured storage root."
            ) from exc

        return destination

    def inspect_archive(
        self,
        path: str | Path,
    ) -> dict[str, Any]:
        """Inspect a supported archive without extracting it."""

        archive_path = Path(path).resolve(strict=True)

        if zipfile.is_zipfile(archive_path):
            return self._inspect_zip(archive_path)

        try:
            if tarfile.is_tarfile(archive_path):
                return self._inspect_tar(archive_path)
        except (OSError, tarfile.TarError):
            pass

        suffixes = {
            suffix.casefold()
            for suffix in archive_path.suffixes
        }

        if suffixes & self._ARCHIVE_SUFFIXES:
            # RAR/7z and single-stream gzip/bzip2/xz are stored as opaque
            # evidence for now. Since the application does not extract them,
            # path traversal/decompression bombs cannot cross into storage.
            return {
                "archive_detected": True,
                "format": archive_path.suffix.lower().lstrip(".") or "unknown",
                "inspection": "opaque",
                "member_count": None,
                "total_uncompressed_bytes": None,
                "nested_archive_candidates": None,
                "extraction_allowed": False,
                "warnings": [
                    "Archive is stored as opaque evidence; automatic extraction is disabled."
                ],
            }

        return {
            "archive_detected": False,
            "format": None,
            "inspection": "not_archive",
            "member_count": 0,
            "total_uncompressed_bytes": 0,
            "nested_archive_candidates": 0,
            "extraction_allowed": False,
            "warnings": [],
        }

    def _inspect_zip(
        self,
        path: Path,
    ) -> dict[str, Any]:
        total_uncompressed = 0
        nested_candidates = 0

        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()

            if len(members) > self.max_archive_members:
                raise UntrustedFilePolicyError(
                    "Archive exceeds the member-count security limit."
                )

            for info in members:
                normalized_name = self._validate_archive_member_name(
                    info.filename
                )

                if info.is_dir():
                    continue

                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise UntrustedFilePolicyError(
                        "Archive contains a symbolic-link entry."
                    )

                file_size = int(info.file_size)
                compressed_size = int(info.compress_size)

                self._validate_archive_member_size(
                    file_size
                )

                total_uncompressed += file_size
                self._validate_archive_total(
                    total_uncompressed
                )

                if file_size > 0:
                    ratio = file_size / max(1, compressed_size)
                    if ratio > self.max_archive_compression_ratio:
                        raise UntrustedFilePolicyError(
                            "Archive member exceeds the compression-ratio security limit."
                        )

                if self._looks_like_archive(normalized_name):
                    nested_candidates += 1
                    self._validate_nested_archive_count(
                        nested_candidates
                    )

        return {
            "archive_detected": True,
            "format": "zip",
            "inspection": "metadata_preflight",
            "member_count": len(members),
            "total_uncompressed_bytes": total_uncompressed,
            "nested_archive_candidates": nested_candidates,
            "extraction_allowed": False,
            "warnings": [
                "Automatic archive extraction is disabled."
            ],
        }

    def _inspect_tar(
        self,
        path: Path,
    ) -> dict[str, Any]:
        member_count = 0
        total_uncompressed = 0
        nested_candidates = 0

        try:
            archive = tarfile.open(
                path,
                mode="r:*",
                errorlevel=1,
            )
        except (tarfile.TarError, OSError) as exc:
            raise UntrustedFilePolicyError(
                "Unable to inspect TAR archive safely."
            ) from exc

        with archive:
            for member in archive:
                member_count += 1

                if member_count > self.max_archive_members:
                    raise UntrustedFilePolicyError(
                        "Archive exceeds the member-count security limit."
                    )

                normalized_name = self._validate_archive_member_name(
                    member.name
                )

                if (
                    member.issym()
                    or member.islnk()
                    or member.isdev()
                    or member.isfifo()
                ):
                    raise UntrustedFilePolicyError(
                        "Archive contains a link or special-file entry."
                    )

                if member.isdir():
                    continue

                if not member.isfile():
                    raise UntrustedFilePolicyError(
                        "Archive contains an unsupported non-regular entry."
                    )

                file_size = int(member.size)

                self._validate_archive_member_size(
                    file_size
                )

                total_uncompressed += file_size
                self._validate_archive_total(
                    total_uncompressed
                )

                if self._looks_like_archive(normalized_name):
                    nested_candidates += 1
                    self._validate_nested_archive_count(
                        nested_candidates
                    )

        return {
            "archive_detected": True,
            "format": "tar",
            "inspection": "metadata_preflight",
            "member_count": member_count,
            "total_uncompressed_bytes": total_uncompressed,
            "nested_archive_candidates": nested_candidates,
            "extraction_allowed": False,
            "warnings": [
                "Automatic archive extraction is disabled."
            ],
        }

    def _validate_archive_member_name(
        self,
        value: str,
    ) -> str:
        raw = str(value or "").replace("\\", "/")

        if not raw or "\x00" in raw:
            raise UntrustedFilePolicyError(
                "Archive contains an invalid member path."
            )

        if raw.startswith("/") or raw.startswith("//"):
            raise UntrustedFilePolicyError(
                "Archive contains an absolute member path."
            )

        if re.match(r"^[A-Za-z]:", raw):
            raise UntrustedFilePolicyError(
                "Archive contains a drive-qualified member path."
            )

        path = PurePosixPath(raw)

        if ".." in path.parts:
            raise UntrustedFilePolicyError(
                "Archive contains a path-traversal member."
            )

        meaningful_parts = [
            part
            for part in path.parts
            if part not in {"", "."}
        ]

        if len(meaningful_parts) > self.max_archive_path_depth:
            raise UntrustedFilePolicyError(
                "Archive member exceeds the path-depth security limit."
            )

        if any(":" in part for part in meaningful_parts):
            raise UntrustedFilePolicyError(
                "Archive member contains a non-portable path component."
            )

        return "/".join(meaningful_parts)

    def _validate_archive_member_size(
        self,
        size_bytes: int,
    ) -> None:
        if size_bytes < 0:
            raise UntrustedFilePolicyError(
                "Archive contains an invalid member size."
            )

        if size_bytes > self.max_archive_member_size_bytes:
            raise UntrustedFilePolicyError(
                "Archive member exceeds the uncompressed-size security limit."
            )

    def _validate_archive_total(
        self,
        total_bytes: int,
    ) -> None:
        if total_bytes > self.max_archive_total_uncompressed_bytes:
            raise UntrustedFilePolicyError(
                "Archive exceeds the total uncompressed-size security limit."
            )

    def _validate_nested_archive_count(
        self,
        count: int,
    ) -> None:
        if count > self.max_nested_archive_candidates:
            raise UntrustedFilePolicyError(
                "Archive contains too many nested-archive candidates."
            )

    @classmethod
    def _looks_like_archive(
        cls,
        value: str,
    ) -> bool:
        lowered = value.casefold()

        return any(
            lowered.endswith(suffix)
            for suffix in cls._ARCHIVE_SUFFIXES
        )


__all__ = [
    "UntrustedFilePolicy",
    "UntrustedFilePolicyError",
]
