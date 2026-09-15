"""Resolve current official Ukraine EDR UO/FOP resources without downloading them."""
from __future__ import annotations

import json

from app.infrastructure.registries.ukraine_edr_downloader import UaEdrDatasetClient


def _resource_payload(resource) -> dict:
    return {
        "name": resource.name,
        "resource_id": resource.resource_id,
        "url": resource.url,
        "modified_at": resource.modified_at,
        "hash": resource.hash_value,
    }


def main() -> int:
    resources = UaEdrDatasetClient().resolve_latest()
    print(
        json.dumps(
            {
                "dataset_id": resources.dataset_id,
                "dataset_modified_at": resources.modified_at,
                "fingerprint": resources.fingerprint,
                "uo": _resource_payload(resources.uo),
                "fop": _resource_payload(resources.fop),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
