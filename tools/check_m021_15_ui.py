from pathlib import Path

def main():
    page = Path("app/interface/desktop/pages/case_workspace_page.py").read_text(encoding="utf-8")
    view = Path("app/interface/desktop/views/workspace/case_workspace_view.py").read_text(encoding="utf-8")
    widget = Path("app/interface/desktop/views/workspace/investigation_search_view.py").read_text(encoding="utf-8")
    worker = Path("app/interface/desktop/workers/investigation_search_worker.py").read_text(encoding="utf-8")

    checks = [
        ("Case Workspace search signal", "investigation_search_requested.connect(" in page),
        ("background QThread", "InvestigationSearchWorker" in page and "QThread(self)" in page),
        ("existing container reused", "container=self.container" in page and "ServiceContainer(" not in page),
        ("Open-Web service reused", "open_web_enrichment_service.enrich" in worker),
        ("controlled recursion opt-in", "if self.recursive:" in worker and "open_web_recursive_pivot_service.expand" in worker),
        ("search tab present", "_create_investigation_search_tab" in view),
        ("Overview Entities Sources", all(x in widget for x in ('"Обзор"', '"Сущности"', '"Источники"'))),
        ("commit on success", "self.container.commit()" in page),
        ("rollback on failure", "self.container.rollback()" in page),
    ]

    print("=" * 72)
    print("M021.15 INVESTIGATION SEARCH UI AUDIT")
    print("=" * 72)
    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print("\nPolicy:")
    print("- One Case Workspace tab.")
    print("- No second ServiceContainer.")
    print("- Search runs outside the UI thread.")
    print("- Recursive expansion is opt-in and disabled by default.")
    print("- Existing Open-Web/WARC/extraction/persistence services are reused.")
    print("- No DB migration.")
    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
