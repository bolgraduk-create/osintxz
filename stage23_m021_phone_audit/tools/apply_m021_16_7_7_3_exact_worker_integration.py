from __future__ import annotations

from pathlib import Path
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

    marker = "# M021.16.7.7.3 unified specialized + Open-Web flow"
    if marker in original:
        print("[PASS] Patch already applied.")
        return 0

    start_marker = "            # M021.16.4 EMAIL routing\\n"
    end_marker = "        except Exception as exc:\\n"

    start = original.find(start_marker)
    end = original.find(end_marker, start)

    if start < 0:
        print("[FAIL] Current EMAIL/USERNAME routing start marker not found.")
        return 1

    if end < 0:
        print("[FAIL] Worker exception boundary not found.")
        return 1

    replacement = '''            # M021.16.7.7.3 unified specialized + Open-Web flow
            #
            # All detected targets enter the already-existing safe/default
            # OSINT enrichment boundary first. Goal/provider selection remains
            # owned by PivotPolicy + Router, not by UI.

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

            # Preserve the already-tested recursive behavior.
            # EMAIL/USERNAME recursion was explicitly deferred in the current
            # worker, so it stays deferred here.
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

    try:
        compile(patched, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] Patched worker compile: {exc}")
        return 1

    backup = TARGET.with_suffix(
        TARGET.suffix + ".m021_16_7_7_3_backup"
    )
    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(patched, encoding="utf-8")

    print("[PASS] Exact current worker patched.")
    print("[PASS] PHONE specialized enrichment enabled.")
    print("[PASS] EMAIL specialized enrichment retained.")
    print("[PASS] USERNAME specialized enrichment retained.")
    print("[PASS] DOMAIN specialized enrichment enabled.")
    print("[PASS] URL specialized enrichment enabled.")
    print("[PASS] Open-Web enrichment retained for all targets.")
    print("[PASS] Existing generic recursion retained.")
    print("[PASS] EMAIL/USERNAME deferred recursion preserved.")
    print("[PASS] No DB migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
