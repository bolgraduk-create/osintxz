"""Official data.gov.ua discovery and bounded download for Ukraine EDRSR.

The Registry Backend is the only component allowed to mirror these yearly
archives. End-user desktops query the backend and never download the national
court-decision dataset.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import httpx


CKAN_PACKAGE_SEARCH = "https://data.gov.ua/api/3/action/package_search"
CKAN_RESOURCE_SHOW = "https://data.gov.ua/api/3/action/resource_show"
OFFICIAL_DATASET_PAGE = "https://data.gov.ua/dataset/{dataset_id}"
OFFICIAL_ORGANIZATION_ID = "b5ee25dd-1516-4a2a-a9cb-7afb5e8ec61a"


@dataclass(frozen=True, slots=True)
class UaEdrsrResource:
    name: str
    resource_id: str
    url: str
    modified_at: str | None = None
    hash_value: str | None = None


@dataclass(frozen=True, slots=True)
class UaEdrsrDatasetResources:
    dataset_year: int
    dataset_id: str
    dataset_name: str
    modified_at: str | None
    resource: UaEdrsrResource

    @property
    def fingerprint(self) -> str:
        payload = "|".join(
            [
                str(self.dataset_year),
                self.dataset_id,
                self.resource.resource_id,
                self.resource.hash_value or self.resource.modified_at or "",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    @property
    def dataset_page(self) -> str:
        return OFFICIAL_DATASET_PAGE.format(dataset_id=self.dataset_id)


@dataclass(frozen=True, slots=True)
class UaEdrsrDownloadedFile:
    path: Path
    size_bytes: int
    sha256: str


class UaEdrsrDatasetClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": "OSINTXZ/RegistryIntelligence"},
        )

    def resolve_year(
        self,
        dataset_year: int,
        *,
        timeout: int = 30,
    ) -> UaEdrsrDatasetResources:
        year = self._normalize_year(dataset_year)
        response = self.client.get(
            CKAN_PACKAGE_SEARCH,
            params={
                "q": f"Єдиний державний реєстр судових рішень за {year} рік",
                "rows": 50,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success") or not isinstance(payload.get("result"), dict):
            raise RuntimeError("data.gov.ua returned an invalid EDRSR discovery response.")

        candidates = payload["result"].get("results") or []
        resolved: list[tuple[int, UaEdrsrDatasetResources]] = []
        for raw in candidates:
            if not isinstance(raw, dict):
                continue
            resource = self._find_archive(raw.get("resources") or [], year)
            if resource is None:
                continue

            title = str(raw.get("title") or raw.get("name") or "").strip()
            dataset_id = str(raw.get("id") or "").strip()
            if not dataset_id:
                continue

            score = self._dataset_score(raw, title=title, year=year)
            if score <= 0:
                continue
            resolved.append(
                (
                    score,
                    UaEdrsrDatasetResources(
                        dataset_year=year,
                        dataset_id=dataset_id,
                        dataset_name=str(raw.get("name") or title).strip(),
                        modified_at=(
                            str(raw.get("metadata_modified") or "").strip() or None
                        ),
                        resource=resource,
                    ),
                )
            )

        if not resolved:
            raise RuntimeError(
                f"Unable to resolve official Ukraine EDRSR archive for {year} from data.gov.ua."
            )

        resolved.sort(key=lambda item: item[0], reverse=True)
        selected = resolved[0][1]
        enriched_resource = self._resolve_resource_metadata(
            selected.resource,
            timeout=timeout,
        )
        return UaEdrsrDatasetResources(
            dataset_year=selected.dataset_year,
            dataset_id=selected.dataset_id,
            dataset_name=selected.dataset_name,
            modified_at=selected.modified_at,
            resource=enriched_resource,
        )


    def _resolve_resource_metadata(
        self,
        resource: UaEdrsrResource,
        *,
        timeout: int,
    ) -> UaEdrsrResource:
        """Refresh the selected resource through CKAN resource_show.

        package_search may expose incomplete resource metadata for frequently
        revised files. resource_show is the official CKAN endpoint for the
        current resource metadata and is used here before any download so the
        backend can consume the portal-provided checksum when available.
        """
        if not resource.resource_id:
            raise RuntimeError("Resolved EDRSR resource does not have a resource id.")

        response = self.client.get(
            CKAN_RESOURCE_SHOW,
            params={"id": resource.resource_id},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("result")
        if not payload.get("success") or not isinstance(raw, dict):
            raise RuntimeError("data.gov.ua returned invalid EDRSR resource metadata.")

        resolved_id = str(raw.get("id") or "").strip()
        if resolved_id and resolved_id != resource.resource_id:
            raise RuntimeError("data.gov.ua returned metadata for a different EDRSR resource.")

        name = str(raw.get("name") or raw.get("title") or resource.name).strip()
        url = str(raw.get("url") or resource.url).strip()
        self._validate_official_url(url)
        return self._resource_from_raw(
            {
                **raw,
                "id": resource.resource_id,
                "name": name,
                "url": url,
                "last_modified": (
                    raw.get("last_modified")
                    or raw.get("metadata_modified")
                    or resource.modified_at
                ),
                "hash": raw.get("hash") or resource.hash_value,
            },
            name=name,
            url=url,
        )

    @staticmethod
    def _dataset_score(raw: dict, *, title: str, year: int) -> int:
        normalized = title.casefold()
        if str(year) not in normalized:
            return 0
        required = ("єдиний", "держав", "реєстр", "судов", "ріш")
        if not all(token in normalized for token in required):
            return 0

        score = 100
        organization = raw.get("organization")
        if isinstance(organization, dict):
            organization_id = str(organization.get("id") or "").strip()
            organization_title = str(organization.get("title") or "").casefold()
            if organization_id == OFFICIAL_ORGANIZATION_ID:
                score += 30
            if "судова адміністрація" in organization_title:
                score += 20
        if str(raw.get("state") or "").casefold() == "active":
            score += 5
        return score

    @staticmethod
    def _find_archive(resources, year: int) -> UaEdrsrResource | None:
        exact = f"edrsr_data_{year}.zip"
        fallback: UaEdrsrResource | None = None
        for raw in resources:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("title") or "").strip()
            url = str(raw.get("url") or "").strip()
            fmt = str(raw.get("format") or "").strip().casefold()
            if not url:
                continue
            normalized = name.casefold()
            if normalized == exact.casefold():
                UaEdrsrDatasetClient._validate_official_url(url)
                return UaEdrsrDatasetClient._resource_from_raw(raw, name=name, url=url)
            if (
                fallback is None
                and "edrsr" in normalized
                and str(year) in normalized
                and (normalized.endswith(".zip") or fmt == "zip")
            ):
                UaEdrsrDatasetClient._validate_official_url(url)
                fallback = UaEdrsrDatasetClient._resource_from_raw(raw, name=name, url=url)
        return fallback

    @staticmethod
    def _resource_from_raw(raw: dict, *, name: str, url: str) -> UaEdrsrResource:
        return UaEdrsrResource(
            name=name,
            resource_id=str(raw.get("id") or "").strip(),
            url=url,
            modified_at=(
                str(raw.get("last_modified") or raw.get("metadata_modified") or "").strip()
                or None
            ),
            hash_value=str(raw.get("hash") or "").strip() or None,
        )

    def download(
        self,
        resource: UaEdrsrResource,
        destination: Path,
        *,
        timeout: int = 900,
        max_bytes: int = 8 * 1024 * 1024 * 1024,
    ) -> UaEdrsrDownloadedFile:
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
                    raise ValueError("EDRSR archive exceeds configured compressed download limit.")

                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError(
                                "EDRSR archive exceeded configured compressed download limit."
                            )
                        sha256_digest.update(chunk)
                        md5_digest.update(chunk)
                        handle.write(chunk)

            sha256_value = sha256_digest.hexdigest()
            self._validate_checksum(
                expected=resource.hash_value,
                md5_value=md5_digest.hexdigest(),
                sha256_value=sha256_value,
            )
            temporary.replace(destination)
            return UaEdrsrDownloadedFile(destination, total, sha256_value)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _validated_cached_file(
        self,
        resource: UaEdrsrResource,
        destination: Path,
        *,
        max_bytes: int,
    ) -> UaEdrsrDownloadedFile | None:
        if not destination.is_file():
            return None
        expected = (resource.hash_value or "").strip().casefold()
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
        try:
            self._validate_checksum(
                expected=expected,
                md5_value=md5_digest.hexdigest(),
                sha256_value=sha256_value,
            )
        except ValueError:
            return None
        return UaEdrsrDownloadedFile(destination, size, sha256_value)

    @staticmethod
    def _validate_checksum(
        *,
        expected: str | None,
        md5_value: str,
        sha256_value: str,
    ) -> None:
        normalized = (expected or "").strip().casefold()
        if not normalized:
            return
        if len(normalized) == 32 and all(c in "0123456789abcdef" for c in normalized):
            if md5_value != normalized:
                raise ValueError(
                    "Downloaded EDRSR archive does not match the official MD5 checksum."
                )
            return
        if len(normalized) == 64 and all(c in "0123456789abcdef" for c in normalized):
            if sha256_value != normalized:
                raise ValueError(
                    "Downloaded EDRSR archive does not match the official SHA-256 checksum."
                )

    @staticmethod
    def _normalize_year(value: int) -> int:
        year = int(value)
        if year < 2006 or year > 2100:
            raise ValueError("EDRSR dataset year must be between 2006 and 2100.")
        return year

    @staticmethod
    def _validate_official_url(url: str) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not (
            host == "data.gov.ua" or host.endswith(".data.gov.ua")
        ):
            raise ValueError(
                "Ukraine EDRSR resources must use an official HTTPS data.gov.ua URL."
            )
