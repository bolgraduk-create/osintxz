"""Resolve the official data.gov.ua EDRSR yearly archive without downloading it."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.infrastructure.registries.ukraine_edrsr_downloader import UaEdrsrDatasetClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now(timezone.utc).year,
    )
    args = parser.parse_args()

    resources = UaEdrsrDatasetClient().resolve_year(args.year)
    resource = resources.resource
    print(f"year: {resources.dataset_year}")
    print(f"dataset_id: {resources.dataset_id}")
    print(f"dataset_name: {resources.dataset_name}")
    print(f"dataset_modified_at: {resources.modified_at}")
    print(f"resource_id: {resource.resource_id}")
    print(f"resource_name: {resource.name}")
    print(f"resource_modified_at: {resource.modified_at}")
    print(f"official_hash: {resource.hash_value}")
    print(f"url: {resource.url}")
    print(f"fingerprint: {resources.fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
