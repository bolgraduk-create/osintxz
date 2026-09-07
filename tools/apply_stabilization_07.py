"""
Apply Stabilization 07: retire the legacy EvidenceProcessingService from
the active Telegram import / ServiceContainer production path.

The legacy service file itself is intentionally kept for compatibility.
"""

from __future__ import annotations

from pathlib import Path
import py_compile
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]

SERVICE_CONTAINER = ROOT / "app" / "core" / "service_container.py"
TELEGRAM_IMPORT = ROOT / "app" / "services" / "telegram_import_service.py"

OPTIONAL_TESTS = (
    ROOT / "tests" / "golden_investigation_runtime.py",
    ROOT / "tests" / "test_telegram_identifier_e2e.py",
)


def _backup(path: Path) -> None:
    backup = path.with_name(
        path.name + ".stabilization07.bak"
    )
    if not backup.exists():
        shutil.copy2(path, backup)
        print(f"Backup created: {backup}")


def _write_if_changed(
    path: Path,
    source: str,
    updated: str,
) -> None:
    if updated == source:
        print(f"No changes needed: {path}")
        return

    _backup(path)

    path.write_text(
        updated,
        encoding="utf-8",
        newline="\n",
    )
    print(f"Updated: {path}")


def _remove_import_block(
    source: str,
    module: str,
    imported_name: str,
) -> str:

    pattern = re.compile(
        rf"\n?from {re.escape(module)} import \(\s*"
        rf"{re.escape(imported_name)},?\s*"
        rf"\)\s*\n",
        re.MULTILINE,
    )

    return pattern.sub(
        "\n",
        source,
        count=1,
    )


def patch_telegram_import() -> None:

    if not TELEGRAM_IMPORT.exists():
        raise FileNotFoundError(
            f"Missing: {TELEGRAM_IMPORT}"
        )

    source = TELEGRAM_IMPORT.read_text(
        encoding="utf-8",
    )
    updated = source

    updated = _remove_import_block(
        updated,
        "app.services.evidence_processing_service",
        "EvidenceProcessingService",
    )

    updated = re.sub(
        r"^\s{8}processing_service:\s*EvidenceProcessingService,\s*\n",
        "",
        updated,
        count=1,
        flags=re.MULTILINE,
    )

    updated = re.sub(
        r"\n\s{8}self\.processing_service\s*=\s*\(\s*\n"
        r"\s{12}processing_service\s*\n"
        r"\s{8}\)\s*\n",
        "\n",
        updated,
        count=1,
        flags=re.MULTILINE,
    )

    # Remove the stale disabled block that references the old service.
    updated = re.sub(
        r"\n\s{8}# ------------------------------------------------------\n"
        r"\s{8}# AI processing\n"
        r"\s{8}# ------------------------------------------------------\n"
        r"(?:\s{8}#.*\n|\s*\n)*?"
        r"\s{8}# self\.processing_service\.process_case\(\n"
        r"\s{8}#     case_id\n"
        r"\s{8}# \)\n",
        "\n"
        "        # ------------------------------------------------------\n"
        "        # Post-import analysis\n"
        "        # ------------------------------------------------------\n"
        "        # Full investigation analysis is intentionally not run\n"
        "        # inside Telegram import. The caller may invoke the\n"
        "        # application-level InvestigationAnalysisRunner after the\n"
        "        # import transaction has completed successfully.\n",
        updated,
        count=1,
        flags=re.MULTILINE,
    )

    _write_if_changed(
        TELEGRAM_IMPORT,
        source,
        updated,
    )

    py_compile.compile(
        str(TELEGRAM_IMPORT),
        doraise=True,
    )

    final = TELEGRAM_IMPORT.read_text(
        encoding="utf-8",
    )

    forbidden = (
        "EvidenceProcessingService",
        "processing_service:",
        "self.processing_service",
    )

    found = [
        value
        for value in forbidden
        if value in final
    ]

    if found:
        raise RuntimeError(
            "TelegramImportService still contains retired dependency: "
            + ", ".join(found)
        )

    print("TelegramImportService retirement check: PASS")


def patch_service_container() -> None:

    if not SERVICE_CONTAINER.exists():
        raise FileNotFoundError(
            f"Missing: {SERVICE_CONTAINER}"
        )

    source = SERVICE_CONTAINER.read_text(
        encoding="utf-8",
    )
    updated = source

    updated = _remove_import_block(
        updated,
        "app.services.evidence_processing_service",
        "EvidenceProcessingService",
    )

    # Remove the complete legacy Evidence Processing composition block.
    updated = re.sub(
        r"\n\s{8}# ==================================================\n"
        r"\s{8}# Evidence Processing\n"
        r"\s{8}# ==================================================\n"
        r"\s*\n"
        r"\s{8}self\.evidence_processing_service\s*=\s*\(\n"
        r".*?"
        r"\s{8}\)\n"
        r"\s*\n"
        r"(?=\s{8}# ==================================================\n"
        r"\s{8}# Telegram Entity Import)",
        "\n",
        updated,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    # Remove the now-dead constructor keyword from TelegramImportService.
    updated = re.sub(
        r"\n\s{16}processing_service=\(\n"
        r"\s{20}self\.evidence_processing_service\n"
        r"\s{16}\),",
        "",
        updated,
        count=1,
        flags=re.MULTILINE,
    )

    _write_if_changed(
        SERVICE_CONTAINER,
        source,
        updated,
    )

    py_compile.compile(
        str(SERVICE_CONTAINER),
        doraise=True,
    )

    final = SERVICE_CONTAINER.read_text(
        encoding="utf-8",
    )

    forbidden = (
        "EvidenceProcessingService(",
        "self.evidence_processing_service =",
        "processing_service=(\n                    self.evidence_processing_service",
    )

    found = [
        value
        for value in forbidden
        if value in final
    ]

    if found:
        raise RuntimeError(
            "ServiceContainer still contains active legacy processing wiring."
        )

    required = (
        "self.investigation_analysis_orchestrator =",
        "self.investigation_analysis_runner =",
    )

    missing = [
        value
        for value in required
        if value not in final
    ]

    if missing:
        raise RuntimeError(
            "Modern investigation wiring is missing: "
            + ", ".join(missing)
        )

    print("ServiceContainer retirement check: PASS")


def patch_tests() -> None:

    for path in OPTIONAL_TESTS:

        if not path.exists():
            print(f"Optional test not found, skipped: {path}")
            continue

        source = path.read_text(
            encoding="utf-8",
        )

        updated = re.sub(
            r"^\s{8}processing_service=SimpleNamespace\(\),\s*\n",
            "",
            source,
            flags=re.MULTILINE,
        )

        _write_if_changed(
            path,
            source,
            updated,
        )

        py_compile.compile(
            str(path),
            doraise=True,
        )


def main() -> None:

    patch_telegram_import()
    patch_service_container()
    patch_tests()

    print("")
    print("Stabilization 07: PASS")
    print(
        "Legacy EvidenceProcessingService remains on disk for compatibility, "
        "but is no longer part of the active Telegram/ServiceContainer path."
    )


if __name__ == "__main__":
    main()
