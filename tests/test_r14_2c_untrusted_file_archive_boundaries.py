from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile
import zipfile

import pytest

from app.security.untrusted_file_policy import (
    UntrustedFilePolicy,
    UntrustedFilePolicyError,
)


def _write_zip(
    path: Path,
    members: list[tuple[str, bytes]],
) -> None:
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, payload in members:
            archive.writestr(name, payload)


def test_source_file_size_is_bounded(tmp_path):
    path = tmp_path / "large.bin"
    path.write_bytes(b"123456789")

    policy = UntrustedFilePolicy(
        max_file_size_bytes=8
    )

    with pytest.raises(
        UntrustedFilePolicyError,
        match="size limit",
    ):
        policy.validate_source_path(path)


def test_managed_destination_cannot_escape_root(tmp_path):
    root = tmp_path / "managed"
    root.mkdir()

    policy = UntrustedFilePolicy()

    safe = policy.validate_managed_destination(
        storage_root=root,
        destination_path=root / "case" / "file.txt",
    )

    assert safe.is_relative_to(root.resolve())

    with pytest.raises(
        UntrustedFilePolicyError,
        match="escapes",
    ):
        policy.validate_managed_destination(
            storage_root=root,
            destination_path=root / ".." / "escape.txt",
        )


def test_safe_zip_preflight_never_enables_extraction(tmp_path):
    path = tmp_path / "safe.zip"
    _write_zip(
        path,
        [
            ("docs/a.txt", b"hello"),
            ("docs/b.txt", b"world"),
        ],
    )

    result = UntrustedFilePolicy().inspect_archive(path)

    assert result["archive_detected"] is True
    assert result["format"] == "zip"
    assert result["member_count"] == 2
    assert result["total_uncompressed_bytes"] == 10
    assert result["extraction_allowed"] is False


@pytest.mark.parametrize(
    "member_name",
    [
        "../escape.txt",
        "folder/../../escape.txt",
        "/absolute.txt",
        "C:/windows/escape.txt",
        r"..\escape.txt",
    ],
)
def test_zip_path_traversal_and_absolute_paths_are_rejected(
    tmp_path,
    member_name,
):
    path = tmp_path / "bad.zip"
    _write_zip(
        path,
        [(member_name, b"payload")],
    )

    with pytest.raises(UntrustedFilePolicyError):
        UntrustedFilePolicy().inspect_archive(path)


def test_zip_member_count_is_bounded(tmp_path):
    path = tmp_path / "many.zip"
    _write_zip(
        path,
        [
            ("a.txt", b"a"),
            ("b.txt", b"b"),
            ("c.txt", b"c"),
        ],
    )

    policy = UntrustedFilePolicy(
        max_archive_members=2
    )

    with pytest.raises(
        UntrustedFilePolicyError,
        match="member-count",
    ):
        policy.inspect_archive(path)


def test_zip_total_uncompressed_size_is_bounded(tmp_path):
    path = tmp_path / "large.zip"
    _write_zip(
        path,
        [
            ("a.txt", b"A" * 20),
            ("b.txt", b"B" * 20),
        ],
    )

    policy = UntrustedFilePolicy(
        max_archive_total_uncompressed_bytes=30,
        max_archive_compression_ratio=10_000,
    )

    with pytest.raises(
        UntrustedFilePolicyError,
        match="total uncompressed-size",
    ):
        policy.inspect_archive(path)


def test_zip_compression_ratio_is_bounded(tmp_path):
    path = tmp_path / "ratio.zip"
    _write_zip(
        path,
        [("bomb.txt", b"A" * 100_000)],
    )

    policy = UntrustedFilePolicy(
        max_archive_compression_ratio=10.0,
        max_archive_member_size_bytes=200_000,
        max_archive_total_uncompressed_bytes=200_000,
    )

    with pytest.raises(
        UntrustedFilePolicyError,
        match="compression-ratio",
    ):
        policy.inspect_archive(path)


def test_tar_path_traversal_is_rejected(tmp_path):
    path = tmp_path / "bad.tar"

    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo("../escape.txt")
        payload = b"payload"
        info.size = len(payload)
        archive.addfile(
            info,
            BytesIO(payload),
        )

    with pytest.raises(
        UntrustedFilePolicyError,
        match="path-traversal",
    ):
        UntrustedFilePolicy().inspect_archive(path)


def test_tar_links_are_rejected(tmp_path):
    path = tmp_path / "link.tar"

    with tarfile.open(path, "w") as archive:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)

    with pytest.raises(
        UntrustedFilePolicyError,
        match="link or special-file",
    ):
        UntrustedFilePolicy().inspect_archive(path)


def test_opaque_archive_formats_are_stored_without_extraction(tmp_path):
    path = tmp_path / "sample.7z"
    path.write_bytes(b"not-a-real-7z-but-still-opaque")

    result = UntrustedFilePolicy().inspect_archive(path)

    assert result["archive_detected"] is True
    assert result["inspection"] == "opaque"
    assert result["extraction_allowed"] is False
