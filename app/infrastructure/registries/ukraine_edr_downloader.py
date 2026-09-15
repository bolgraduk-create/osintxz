"""Official data.gov.ua EDR resource discovery and bounded download."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import httpx


DATASET_IDS = (
    "a1799820-195b-4982-8141-6e84f58103e7",
    "03cc1239-3988-4451-aa0d-aadb77448714",
)
CKAN_PACKAGE_SHOW = "https://data.gov.ua/api/3/action/package_show"
OFFICIAL_DATASET_PAGE = (
    "https://data.gov.ua/dataset/a1799820-195b-4982-8141-6e84f58103e7"
)


@dataclass(frozen=True, slots=True)
class UaEdrResource:
    name: str
    resource_id: str
    url: str
    modified_at: str | None = None
    hash_value: str | None = None


@dataclass(frozen=True, slots=True)
class UaEdrDatasetResources:
    dataset_id: str
    modified_at: str | None
    uo: UaEdrResource
    fop: UaEdrResource

    @property
    def fingerprint(self) -> str:
        payload = "|".join(
            [
                self.dataset_id,
                self.uo.resource_id,
                self.uo.hash_value or self.uo.modified_at or "",
                self.fop.resource_id,
                self.fop.hash_value or self.fop.modified_at or "",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class UaEdrDownloadedFile:
    path: Path
    size_bytes: int
    sha256: str


class UaEdrDatasetClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": "OSINTXZ/RegistryIntelligence"},
        )

    def resolve_latest(self, *, timeout: int = 30) -> UaEdrDatasetResources:
        last_error: Exception | None = None
        for dataset_id in DATASET_IDS:
            try:
                response = self.client.get(
                    CKAN_PACKAGE_SHOW,
                    params={"id": dataset_id},
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not payload.get("success") or not isinstance(payload.get("result"), dict):
                    continue
                result = payload["result"]
                resources = result.get("resources") or []
                uo = self._find_resource(resources, "uo.zip")
                fop = self._find_resource(resources, "fop.zip")
                if uo and fop:
                    return UaEdrDatasetResources(
                        dataset_id=str(result.get("id") or dataset_id),
                        modified_at=str(result.get("metadata_modified") or "") or None,
                        uo=uo,
                        fop=fop,
                    )
            except Exception as exc:  # isolated discovery attempts
                last_error = exc
        raise RuntimeError(
            "Unable to resolve official Ukraine EDR UO/FOP resources from data.gov.ua."
        ) from last_error

    @staticmethod
    def _find_resource(resources, target_name: str) -> UaEdrResource | None:
        target = target_name.casefold()
        for raw in resources:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("title") or "").strip()
            url = str(raw.get("url") or "").strip()
            if name.casefold() != target or not url:
                continue
            UaEdrDatasetClient._validate_official_url(url)
            return UaEdrResource(
                name=name,
                resource_id=str(raw.get("id") or "").strip(),
                url=url,
                modified_at=str(raw.get("last_modified") or raw.get("metadata_modified") or "") or None,
                hash_value=str(raw.get("hash") or "").strip() or None,
            )
        return None

    def download(
        self,
        resource: UaEdrResource,
        destination: Path,
        *,
        timeout: int = 600,
        max_bytes: int = 4 * 1024 * 1024 * 1024,
    ) -> UaEdrDownloadedFile:
        self._validate_official_url(resource.url)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        cached = self._validated_cached_file(resource, destination, max_bytes=max_bytes)
        if cached is not None:
            return cached

        temporary = destination.with_suffix(destination.suffix + ".part")
        temporary.unlink(missing_ok=True)

        sha256_digest = hashlib.sha256()
        md5_digest = hashlib.md5(usedforsecurity=False)
        total = 0
        try:
            with self.client.stream("GET", resource.url, timeout=timeout) as response:
                response.raise_for_status()
                self._validate_official_url(str(response.url))
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise ValueError("EDR archive exceeds configured compressed download limit.")
                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("EDR archive exceeded configured compressed download limit.")
                        sha256_digest.update(chunk)
                        md5_digest.update(chunk)
                        handle.write(chunk)

            sha256_value = sha256_digest.hexdigest()
            md5_value = md5_digest.hexdigest()
            expected = (resource.hash_value or "").strip().casefold()
            if expected:
                if len(expected) == 32 and all(c in "0123456789abcdef" for c in expected):
                    if md5_value != expected:
                        raise ValueError("Downloaded EDR archive does not match the official MD5 checksum.")
                elif len(expected) == 64 and all(c in "0123456789abcdef" for c in expected):
                    if sha256_value != expected:
                        raise ValueError("Downloaded EDR archive does not match the official SHA-256 checksum.")

            temporary.replace(destination)
            return UaEdrDownloadedFile(destination, total, sha256_value)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


    def _validated_cached_file(
        self,
        resource: UaEdrResource,
        destination: Path,
        *,
        max_bytes: int,
    ) -> UaEdrDownloadedFile | None:
        """Reuse an already downloaded official archive only after checksum validation."""
        if not destination.is_file():
            return None

        expected = (resource.hash_value or "").strip().casefold()
        # Without an official checksum we intentionally re-download rather than
        # trusting a stale/partial server cache entry.
        if not expected:
            return None

        try:
            size = destination.stat().st_size
        except OSError:
            return None
        if size <= 0 or size > max_bytes:
            return None

        sha256_digest = hashlib.sha256()
        md5_digest = hashlib.md5(usedforsecurity=False)
        try:
            with destination.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    sha256_digest.update(chunk)
                    md5_digest.update(chunk)
        except OSError:
            return None

        sha256_value = sha256_digest.hexdigest()
        md5_value = md5_digest.hexdigest()
        if len(expected) == 32 and all(c in "0123456789abcdef" for c in expected):
            valid = md5_value == expected
        elif len(expected) == 64 and all(c in "0123456789abcdef" for c in expected):
            valid = sha256_value == expected
        else:
            return None

        if not valid:
            return None
        return UaEdrDownloadedFile(destination, size, sha256_value)

    @staticmethod
    def _validate_official_url(url: str) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not (host == "data.gov.ua" or host.endswith(".data.gov.ua")):
            raise ValueError("Ukraine EDR resources must use an official HTTPS data.gov.ua URL.")
