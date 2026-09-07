"""M021.11 robust Common Crawl ServiceContainer patcher."""
from __future__ import annotations

from pathlib import Path


PATH = Path(
    "app/core/service_container.py"
)

IMPORT_BLOCK = """
from app.infrastructure.open_web.common_crawl_client import (
    CommonCrawlHttpClient,
)
from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)

"""

WIRING_BLOCK = """
        self.common_crawl_http_client = (
            CommonCrawlHttpClient()
        )

        self.common_crawl_open_web_provider = (
            CommonCrawlOpenWebProvider(
                client=(
                    self.common_crawl_http_client
                ),
            )
        )

        self.open_web_provider_registry.register(
            self.common_crawl_open_web_provider
        )

"""


def main() -> int:
    if not PATH.is_file():
        print(
            f"[FAIL] Missing {PATH}"
        )
        return 1

    original = PATH.read_text(
        encoding="utf-8"
    )
    text = original

    # ------------------------------------------------------
    # Imports
    # ------------------------------------------------------
    if (
        "from app.infrastructure.open_web.common_crawl_client import"
        not in text
    ):
        class_anchor = (
            "class ServiceContainer:"
        )

        if class_anchor not in text:
            print(
                "[FAIL] ServiceContainer class anchor "
                "not found."
            )
            return 1

        text = text.replace(
            class_anchor,
            IMPORT_BLOCK + class_anchor,
            1,
        )

    # ------------------------------------------------------
    # Wiring
    # ------------------------------------------------------
    if (
        "self.common_crawl_open_web_provider ="
        not in text
    ):
        # M021.10 guarantees this service exists and that the
        # registry has already been constructed before it.
        discovery_anchor = (
            "        self.open_web_discovery_service ="
        )

        if discovery_anchor not in text:
            print(
                "[FAIL] M021.10 OpenWebDiscoveryService "
                "assignment not found."
            )
            print(
                "[INFO] No production file was modified."
            )
            return 1

        # Defensive check: registry must occur before discovery.
        registry_pos = text.find(
            "self.open_web_provider_registry"
        )
        discovery_pos = text.find(
            discovery_anchor
        )

        if (
            registry_pos < 0
            or registry_pos > discovery_pos
        ):
            print(
                "[FAIL] Open-Web registry is not available "
                "before discovery service wiring."
            )
            print(
                "[INFO] No production file was modified."
            )
            return 1

        text = text.replace(
            discovery_anchor,
            WIRING_BLOCK + discovery_anchor,
            1,
        )

    # ------------------------------------------------------
    # Structural guards
    # ------------------------------------------------------
    checks = {
        "common crawl http client": (
            text.count(
                "self.common_crawl_http_client ="
            )
            == 1
        ),
        "common crawl provider": (
            text.count(
                "self.common_crawl_open_web_provider ="
            )
            == 1
        ),
        "open-web registry": (
            text.count(
                "self.open_web_provider_registry ="
            )
            == 1
        ),
        "open-web discovery service": (
            text.count(
                "self.open_web_discovery_service ="
            )
            == 1
        ),
        "open-web enrichment service": (
            text.count(
                "self.open_web_enrichment_service ="
            )
            == 1
        ),
        "osint manager": (
            text.count(
                "self.osint_manager ="
            )
            == 1
        ),
        "osint pipeline": (
            text.count(
                "self.osint_pipeline ="
            )
            == 1
        ),
    }

    failed = [
        name
        for name, ok in checks.items()
        if not ok
    ]

    if failed:
        print(
            "[FAIL] Structural guard failed:"
        )
        for name in failed:
            print(
                f"  - {name}"
            )
        print(
            "[INFO] No production file was modified."
        )
        return 1

    try:
        compile(
            text,
            str(PATH),
            "exec",
        )
    except SyntaxError as exc:
        print(
            "[FAIL] Patched ServiceContainer "
            f"does not compile: {exc}"
        )
        print(
            "[INFO] No production file was modified."
        )
        return 1

    # ------------------------------------------------------
    # Write only after every guard passes
    # ------------------------------------------------------
    backup = PATH.with_suffix(
        ".py.m021_11_backup"
    )

    if (
        text != original
        and not backup.exists()
    ):
        backup.write_text(
            original,
            encoding="utf-8",
        )

    PATH.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "[PASS] M021.11 Common Crawl "
        "Open-Web provider wiring applied."
    )
    print(
        "[PASS] Provider registered before "
        "OpenWebDiscoveryService construction."
    )

    if backup.exists():
        print(
            f"[INFO] Backup: {backup}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
