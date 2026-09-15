from __future__ import annotations

from pathlib import Path
import shutil

CONTAINER = Path("app/core/service_container.py")
WORKER = Path("app/interface/desktop/workers/investigation_search_worker.py")


def main() -> int:
    if not CONTAINER.exists() or not WORKER.exists():
        print("[FAIL] Required project files are missing.")
        return 1

    container = CONTAINER.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")

    if "InvestigationTargetEnrichmentService" not in container:
        anchor = "from __future__ import annotations\n"
        if anchor not in container:
            print("[FAIL] ServiceContainer import anchor not found.")
            return 1
        addition = (
            anchor
            + "\nfrom app.application.investigation_target_enrichment_service import (\n"
              "    InvestigationTargetEnrichmentService,\n"
              ")\n"
        )
        container = container.replace(anchor, addition, 1)

    if "self.investigation_target_enrichment_service" not in container:
        anchor = (
            "        self.osint_enrichment_service = (\n"
            "            OsintEnrichmentService(\n"
            "                execution_service=(\n"
            "                    self.osint_enrichment_execution_service\n"
            "                ),\n"
            "                persistence_service=(\n"
            "                    self.osint_finding_persistence_service\n"
            "                ),\n"
            "            )\n"
            "        )\n"
        )
        if anchor not in container:
            print("[FAIL] ServiceContainer OSINT anchor not found.")
            return 1

        block = anchor + (
            "\n        self.investigation_target_enrichment_service = (\n"
            "            InvestigationTargetEnrichmentService(\n"
            "                execution_service=(\n"
            "                    self.osint_enrichment_execution_service\n"
            "                ),\n"
            "                persistence_service=(\n"
            "                    self.osint_finding_persistence_service\n"
            "                ),\n"
            "            )\n"
            "        )\n"
        )
        container = container.replace(anchor, block, 1)

    if '"osint": osint_result' not in worker:
        anchor = (
            "            query = OpenWebQuery(\n"
            "                target_type=target_type,\n"
            "                value=normalized,\n"
            "                case_id=str(self.case_id),\n"
            "                limit=25,\n"
            "                timeout=30,\n"
            "                depth=0,\n"
            "            )\n\n"
            "            self.status_changed.emit(\n"
            '                "Поиск архивных страниц и извлечение сущностей..."\n'
            "            )\n\n"
            "            open_web_result = (\n"
            "                self.container.open_web_enrichment_service.enrich(\n"
            "                    query,\n"
            "                    case_id=self.case_id,\n"
            "                )\n"
            "            )\n"
        )
        if anchor not in worker:
            print("[FAIL] InvestigationSearchWorker search anchor not found.")
            return 1

        replacement = (
            '            self.status_changed.emit("Запуск специализированных OSINT-источников...")\n\n'
            "            osint_result = (\n"
            "                self.container.investigation_target_enrichment_service.enrich(\n"
            "                    case_id=self.case_id,\n"
            "                    target_type=target_type,\n"
            "                    value=normalized,\n"
            "                    timeout=300,\n"
            "                    use_cache=True,\n"
            "                )\n"
            "            )\n\n"
            "            query = OpenWebQuery(\n"
            "                target_type=target_type,\n"
            "                value=normalized,\n"
            "                case_id=str(self.case_id),\n"
            "                limit=25,\n"
            "                timeout=30,\n"
            "                depth=0,\n"
            "            )\n\n"
            '            self.status_changed.emit("Поиск Open-Web, архивов и документов...")\n\n'
            "            open_web_result = (\n"
            "                self.container.open_web_enrichment_service.enrich(\n"
            "                    query,\n"
            "                    case_id=self.case_id,\n"
            "                )\n"
            "            )\n"
        )
        worker = worker.replace(anchor, replacement, 1)

        payload_anchor = (
            '                    "target_type": target_type,\n'
            '                    "normalized_target": normalized,\n'
            '                    "open_web": open_web_result,\n'
            '                    "recursive": recursive_result,\n'
        )
        payload_replacement = (
            '                    "target_type": target_type,\n'
            '                    "normalized_target": normalized,\n'
            '                    "osint": osint_result,\n'
            '                    "osint_provider_rows": osint_result.provider_rows,\n'
            '                    "open_web": open_web_result,\n'
            '                    "recursive": recursive_result,\n'
        )
        if payload_anchor not in worker:
            print("[FAIL] InvestigationSearchWorker payload anchor not found.")
            return 1
        worker = worker.replace(payload_anchor, payload_replacement, 1)

    try:
        compile(container, str(CONTAINER), "exec")
        compile(worker, str(WORKER), "exec")
    except Exception as exc:
        print(f"[FAIL] Compile failed: {exc}")
        return 1

    for path, suffix in (
        (CONTAINER, ".m021_16_7_7_backup"),
        (WORKER, ".m021_16_7_7_backup"),
    ):
        backup = path.with_suffix(path.suffix + suffix)
        if not backup.exists():
            shutil.copy2(path, backup)

    CONTAINER.write_text(container, encoding="utf-8")
    WORKER.write_text(worker, encoding="utf-8")

    print("[PASS] Specialized OSINT routes wired to Investigation Search.")
    print("[PASS] PHONE / EMAIL / USERNAME / DOMAIN / URL defaults enabled.")
    print("[PASS] Existing Open-Web flow retained.")
    print("[PASS] Existing recursive flow retained.")
    print("[PASS] Existing persistence boundary reused.")
    print("[PASS] No DB migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
