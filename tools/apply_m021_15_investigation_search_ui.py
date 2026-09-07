from __future__ import annotations

from pathlib import Path

PAGE = Path("app/interface/desktop/pages/case_workspace_page.py")
VIEW = Path("app/interface/desktop/views/workspace/case_workspace_view.py")

PAGE_METHODS = '    # ==========================================================\n    # Investigation Search\n    # ==========================================================\n\n    def _start_investigation_search(\n        self,\n        raw_target: str,\n        recursive: bool,\n    ) -> None:\n        if self.case is None:\n            return\n\n        if (\n            self._investigation_search_thread is not None\n            and self._investigation_search_thread.isRunning()\n        ):\n            self.workspace_view.investigation_search_view.set_status(\n                "Поиск уже выполняется."\n            )\n            return\n\n        raw_case_id = self.case.get("id")\n        if raw_case_id is None:\n            self.workspace_view.investigation_search_view.show_error(\n                "У текущего дела отсутствует case_id."\n            )\n            return\n\n        try:\n            case_id = UUID(str(raw_case_id))\n        except (TypeError, ValueError):\n            self.workspace_view.investigation_search_view.show_error(\n                "Некорректный case_id."\n            )\n            return\n\n        view = self.workspace_view.investigation_search_view\n        view.clear_results()\n        view.set_running(True)\n\n        thread = QThread(self)\n        worker = InvestigationSearchWorker(\n            container=self.container,\n            case_id=case_id,\n            raw_target=raw_target,\n            recursive=recursive,\n        )\n        worker.moveToThread(thread)\n\n        thread.started.connect(worker.run)\n        worker.status_changed.connect(view.set_status)\n        worker.result_ready.connect(\n            self._on_investigation_search_result\n        )\n        worker.failed.connect(\n            self._on_investigation_search_error\n        )\n        worker.finished.connect(thread.quit)\n        worker.finished.connect(worker.deleteLater)\n        thread.finished.connect(\n            self._on_investigation_search_thread_finished\n        )\n        thread.finished.connect(thread.deleteLater)\n\n        self._investigation_search_thread = thread\n        self._investigation_search_worker = worker\n        thread.start()\n\n    @Slot(object)\n    def _on_investigation_search_result(\n        self,\n        payload,\n    ) -> None:\n        self._latest_investigation_search_payload = payload\n\n        try:\n            self.container.commit()\n        except Exception as exc:\n            logger.exception("Investigation Search commit failed.")\n            try:\n                self.container.rollback()\n            except Exception:\n                logger.exception("Investigation Search rollback failed.")\n\n            self.workspace_view.investigation_search_view.show_error(\n                f"Не удалось сохранить результаты: {exc}"\n            )\n            return\n\n        self.workspace_view.investigation_search_view.show_result(\n            payload\n        )\n\n        try:\n            self._refresh_workspace()\n        except Exception:\n            logger.exception(\n                "Workspace refresh after Investigation Search failed."\n            )\n\n    @Slot(str)\n    def _on_investigation_search_error(\n        self,\n        message: str,\n    ) -> None:\n        try:\n            self.container.rollback()\n        except Exception:\n            logger.exception("Investigation Search rollback failed.")\n\n        self.workspace_view.investigation_search_view.show_error(\n            message\n        )\n\n    @Slot()\n    def _on_investigation_search_thread_finished(\n        self,\n    ) -> None:\n        self._investigation_search_worker = None\n        self._investigation_search_thread = None\n\n        view = getattr(\n            self.workspace_view,\n            "investigation_search_view",\n            None,\n        )\n        if view is not None:\n            view.set_running(False)\n\n'
VIEW_METHOD = '    # ==========================================================\n    # Investigation Search\n    # ==========================================================\n\n    def _create_investigation_search_tab(\n        self,\n    ) -> None:\n        self.investigation_search_view = InvestigationSearchView(\n            self.tabs\n        )\n\n        self.investigation_search_view.search_requested.connect(\n            self.investigation_search_requested.emit\n        )\n\n        self.investigation_search_tab_index = self.tabs.addTab(\n            self.investigation_search_view,\n            "Investigation Search",\n        )\n\n'


def patch_page():
    original = PAGE.read_text(encoding="utf-8")
    text = original

    worker_import = (
        "from app.interface.desktop.workers.investigation_search_worker import (\n"
        "    InvestigationSearchWorker,\n"
        ")\n\n"
    )

    if "investigation_search_worker import" not in text:
        anchor = "from app.models.evidence import (\n"
        if anchor not in text:
            raise RuntimeError("Page import anchor not found.")
        text = text.replace(anchor, worker_import + anchor, 1)

    if "self._investigation_search_thread:" not in text:
        anchor = "        self._ai_thread: QThread | None = None\n"
        if anchor not in text:
            raise RuntimeError("Page state anchor not found.")
        addition = (
            "        self._investigation_search_thread: QThread | None = None\n"
            "        self._investigation_search_worker: InvestigationSearchWorker | None = None\n"
            "        self._latest_investigation_search_payload: dict | None = None\n\n"
        )
        text = text.replace(anchor, addition + anchor, 1)

    if "investigation_search_requested.connect(" not in text:
        anchor = "        self.workspace_view.import_telegram_requested.connect(\n"
        if anchor not in text:
            raise RuntimeError("Page signal anchor not found.")
        block = (
            "        self.workspace_view.investigation_search_requested.connect(\n"
            "            self._start_investigation_search\n"
            "        )\n\n"
        )
        text = text.replace(anchor, block + anchor, 1)

    if "def _start_investigation_search(" not in text:
        anchor = (
            "    # ==========================================================\n"
            "    # Localization\n"
        )
        if anchor not in text:
            raise RuntimeError("Page localization anchor not found.")
        text = text.replace(anchor, PAGE_METHODS + anchor, 1)

    compile(text, str(PAGE), "exec")
    backup = PAGE.with_suffix(".py.m021_15_backup")
    if text != original and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    PAGE.write_text(text, encoding="utf-8")


def patch_view():
    original = VIEW.read_text(encoding="utf-8")
    text = original

    import_block = (
        "from app.interface.desktop.views.workspace.investigation_search_view import (\n"
        "    InvestigationSearchView,\n"
        ")\n\n"
    )

    if "investigation_search_view import" not in text:
        anchor = (
            "from app.interface.desktop.views.workspace.ai_workspace_view import (\n"
        )
        if anchor not in text:
            raise RuntimeError("View import anchor not found.")
        text = text.replace(anchor, import_block + anchor, 1)

    if "investigation_search_requested = Signal(" not in text:
        anchor = "    import_telegram_requested = Signal()\n"
        if anchor not in text:
            raise RuntimeError("View signal anchor not found.")
        signal_block = (
            "    investigation_search_requested = Signal(\n"
            "        str,\n"
            "        bool,\n"
            "    )\n\n"
        )
        text = text.replace(anchor, signal_block + anchor, 1)

    if "self._create_investigation_search_tab()" not in text:
        anchor = "        self._create_overview_tab()\n"
        if anchor not in text:
            raise RuntimeError("View tab anchor not found.")
        text = text.replace(
            anchor,
            anchor + "        self._create_investigation_search_tab()\n",
            1,
        )

    if "def _create_investigation_search_tab(" not in text:
        anchor = (
            "    # ==========================================================\n"
            "    # Overview\n"
        )
        if anchor not in text:
            raise RuntimeError("View overview anchor not found.")
        text = text.replace(anchor, VIEW_METHOD + anchor, 1)

    compile(text, str(VIEW), "exec")
    backup = VIEW.with_suffix(".py.m021_15_backup")
    if text != original and not backup.exists():
        backup.write_text(original, encoding="utf-8")
    VIEW.write_text(text, encoding="utf-8")


def main():
    if not PAGE.is_file() or not VIEW.is_file():
        print("[FAIL] Required desktop files missing.")
        return 1

    try:
        patch_page()
        patch_view()
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1

    print("[PASS] Investigation Search UI wired into Case Workspace.")
    print("[PASS] Existing ServiceContainer reused.")
    print("[PASS] Background QThread worker added.")
    print("[PASS] Recursive enrichment remains opt-in.")
    print("[PASS] No DB migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
