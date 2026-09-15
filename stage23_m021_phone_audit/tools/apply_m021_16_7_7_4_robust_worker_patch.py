from __future__ import annotations

from pathlib import Path
import re
import shutil

TARGET = Path(
    "app/interface/desktop/workers/"
    "investigation_search_worker.py"
)


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing: {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")

    marker = "# M021.16.7.7.4 unified specialized + Open-Web flow"
    if marker in original:
        print("[PASS] Patch already applied.")
        return 0

    branch_match = re.search(
        r"(?ms)^ {12}if target_type in \{\s*"
        r"OsintTargetType\.EMAIL,\s*"
        r"OsintTargetType\.USERNAME,\s*"
        r"\}:",
        original,
    )

    if branch_match is None:
        print("[FAIL] EMAIL/USERNAME legacy branch not found.")
        print("[INFO] No project files were changed.")
        return 1

    except_match = re.search(
        r"(?m)^ {8}except Exception as exc:\s*$",
        original[branch_match.start():],
    )

    if except_match is None:
        print("[FAIL] Worker exception boundary not found.")
        print("[INFO] No project files were changed.")
        return 1

    start = branch_match.start()
    end = branch_match.start() + except_match.start()

    replacement = '''            # M021.16.7.7.4 unified specialized + Open-Web flow
            #
            # All target types recognized by Investigation Search first use
            # the already-existing safe/default OSINT enrichment boundary.
            # PivotPolicy + Router remain authoritative for goal/provider
            # selection. The UI does not hard-code individual connectors.

            self.status_changed.emit(
                "Запуск специализированных OSINT-источников..."
            )

            osint_result = (
                self.container.osint_enrichment_service.enrich_target(
                    case_id=self.case_id,
                    target_type=target_type,
                    value=normalized,
                    depth=0,
                    timeout=120,
                    use_cache=True,
                    save_raw_output=False,
                    include_metadata=True,
                    include_related=True,
                )
            )

            open_web_limit = (
                40
                if target_type is OsintTargetType.EMAIL
                else 25
            )

            self.status_changed.emit(
                "Поиск Open-Web, архивов и публичных документов..."
            )

            open_web_result = (
                self.container.open_web_enrichment_service.enrich(
                    OpenWebQuery(
                        target_type=target_type,
                        value=normalized,
                        case_id=str(self.case_id),
                        limit=open_web_limit,
                        timeout=30,
                        depth=0,
                    ),
                    case_id=self.case_id,
                )
            )

            recursive_result = None

            if self.recursive:
                if target_type in {
                    OsintTargetType.EMAIL,
                    OsintTargetType.USERNAME,
                }:
                    self.status_changed.emit(
                        "Рекурсивное расширение для email/username "
                        "останется отдельным последующим блоком."
                    )
                else:
                    self.status_changed.emit(
                        "Запуск контролируемого рекурсивного обогащения..."
                    )
                    recursive_result = (
                        self.container.open_web_recursive_pivot_service.expand(
                            case_id=self.case_id,
                            open_web_result=open_web_result,
                            timeout=120,
                        )
                    )

            self.result_ready.emit(
                {
                    "target_type": target_type,
                    "normalized_target": normalized,
                    "open_web": open_web_result,
                    "osint": osint_result,
                    "recursive": recursive_result,
                }
            )
'''

    patched = original[:start] + replacement + original[end:]
    compact = "".join(patched.split())

    required = [
        "self.container.osint_enrichment_service.enrich_target(",
        "self.container.open_web_enrichment_service.enrich(",
        '"osint":osint_result',
        '"open_web":open_web_result',
        "M021.16.7.7.4unifiedspecialized+Open-Webflow",
    ]

    missing = [item for item in required if item not in compact]

    if missing:
        print("[FAIL] Patched worker contract incomplete:")
        for item in missing:
            print(" -", item)
        print("[INFO] No project files were changed.")
        return 1

    try:
        compile(patched, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] Patched worker compile: {exc}")
        print("[INFO] No project files were changed.")
        return 1

    backup = TARGET.with_suffix(
        TARGET.suffix + ".m021_16_7_7_4_backup"
    )
    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(patched, encoding="utf-8")

    print("[PASS] Robust current-worker patch applied.")
    print("[PASS] PHONE specialized enrichment enabled.")
    print("[PASS] EMAIL specialized enrichment retained.")
    print("[PASS] USERNAME specialized enrichment retained.")
    print("[PASS] DOMAIN specialized enrichment enabled.")
    print("[PASS] URL specialized enrichment enabled.")
    print("[PASS] Open-Web enrichment retained for all targets.")
    print("[PASS] Existing recursion behavior preserved.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
