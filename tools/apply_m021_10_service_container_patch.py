"""M021.10 ServiceContainer Open-Web wiring patcher."""
from __future__ import annotations

from pathlib import Path


PATH = Path(
    "app/core/service_container.py"
)

IMPORT_BLOCK = """
from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentService,
)
from app.osint.open_web.extraction_bridge import (
    OpenWebIdentifierExtractionBridge,
)
from app.osint.open_web.registry import (
    OpenWebProviderRegistry,
)
from app.osint.open_web.service import (
    OpenWebDiscoveryService,
)

"""

WIRING_BLOCK = """
        # ==================================================
        # Open-Web Discovery / Enrichment
        # M021.10
        # ==================================================

        self.open_web_provider_registry = (
            OpenWebProviderRegistry()
        )

        self.open_web_discovery_service = (
            OpenWebDiscoveryService(
                registry=(
                    self.open_web_provider_registry
                ),
            )
        )

        self.open_web_identifier_extraction_bridge = (
            OpenWebIdentifierExtractionBridge(
                extraction_service=(
                    self.unified_extraction_service
                ),
            )
        )

        self.open_web_enrichment_service = (
            OpenWebEnrichmentService(
                discovery_service=(
                    self.open_web_discovery_service
                ),
                extraction_bridge=(
                    self.open_web_identifier_extraction_bridge
                ),
                persistence_service=(
                    self.osint_finding_persistence_service
                ),
            )
        )

"""


def _find_assignment_end(
    text: str,
    token: str,
) -> int | None:
    start = text.find(token)
    if start < 0:
        return None

    line_start = text.rfind(
        "\n",
        0,
        start,
    ) + 1

    position = line_start
    depth = 0
    saw_open = False

    while position < len(text):
        char = text[position]

        if char == "(":
            depth += 1
            saw_open = True
        elif char == ")":
            depth -= 1

        if (
            saw_open
            and depth == 0
            and char == "\n"
        ):
            return position + 1

        position += 1

    return None


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

    if (
        "from app.application.open_web_enrichment_service import"
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

    if (
        "self.open_web_enrichment_service ="
        not in text
    ):
        token = (
            "self.osint_finding_persistence_service ="
        )

        end = _find_assignment_end(
            text,
            token,
        )

        if end is None:
            print(
                "[FAIL] "
                "osint_finding_persistence_service "
                "assignment not found."
            )
            return 1

        text = (
            text[:end]
            + WIRING_BLOCK
            + text[end:]
        )

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
        return 1

    backup = PATH.with_suffix(
        ".py.m021_10_backup"
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
        "[PASS] M021.10 ServiceContainer "
        "Open-Web wiring applied."
    )

    if backup.exists():
        print(
            f"[INFO] Backup: {backup}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
