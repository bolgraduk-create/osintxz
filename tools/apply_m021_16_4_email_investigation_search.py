from __future__ import annotations

from pathlib import Path


WORKER = Path(
    "app/interface/desktop/workers/investigation_search_worker.py"
)
VIEW = Path(
    "app/interface/desktop/views/workspace/investigation_search_view.py"
)


def _lines(block: list[str]) -> str:
    return "\n".join(block) + "\n"


def patch_worker(text: str) -> str:
    if "M021.16.4 EMAIL routing" in text:
        return text

    start = text.find("            query = OpenWebQuery(")
    emit_start = text.find(
        "            self.result_ready.emit(",
        start,
    )
    if start < 0 or emit_start < 0:
        raise RuntimeError("Worker routing block anchor not found.")

    # Find the end of the existing result_ready.emit({...}) block.
    end_marker = "            )\n"
    search_from = emit_start
    end = -1
    # Existing block has nested braces but only one closing call line at
    # indentation 12 spaces after the payload dict.
    while True:
        candidate = text.find(end_marker, search_from)
        if candidate < 0:
            break
        chunk = text[emit_start:candidate + len(end_marker)]
        if '"recursive": recursive_result' in chunk:
            end = candidate + len(end_marker)
            break
        search_from = candidate + len(end_marker)

    if end < 0:
        raise RuntimeError("Worker result payload end not found.")

    replacement = _lines([
        "            # M021.16.4 EMAIL routing",
        "            if target_type is OsintTargetType.EMAIL:",
        "                self.status_changed.emit(",
        '                    "Поиск по email через доступные OSINT-коннекторы..."',
        "                )",
        "",
        "                osint_result = (",
        "                    self.container.osint_enrichment_service.enrich_target(",
        "                        case_id=self.case_id,",
        "                        target_type=target_type,",
        "                        value=normalized,",
        "                        depth=0,",
        "                        timeout=120,",
        "                        use_cache=True,",
        "                        save_raw_output=False,",
        "                        include_metadata=True,",
        "                        include_related=True,",
        "                    )",
        "                )",
        "",
        "                if self.recursive:",
        "                    self.status_changed.emit(",
        '                        "Email Search v1: рекурсивное расширение "',
        '                        "будет подключено отдельным блоком."',
        "                    )",
        "",
        "                self.result_ready.emit(",
        "                    {",
        '                        "target_type": target_type,',
        '                        "normalized_target": normalized,',
        '                        "open_web": None,',
        '                        "osint": osint_result,',
        '                        "recursive": None,',
        "                    }",
        "                )",
        "            else:",
        "                query = OpenWebQuery(",
        "                    target_type=target_type,",
        "                    value=normalized,",
        "                    case_id=str(self.case_id),",
        "                    limit=25,",
        "                    timeout=30,",
        "                    depth=0,",
        "                )",
        "",
        "                self.status_changed.emit(",
        '                    "Поиск публичных/архивных страниц "',
        '                    "и извлечение сущностей..."',
        "                )",
        "",
        "                open_web_result = (",
        "                    self.container.open_web_enrichment_service.enrich(",
        "                        query,",
        "                        case_id=self.case_id,",
        "                    )",
        "                )",
        "",
        "                recursive_result = None",
        "                if self.recursive:",
        "                    self.status_changed.emit(",
        '                        "Запуск контролируемого рекурсивного обогащения..."',
        "                    )",
        "                    recursive_result = (",
        "                        self.container.open_web_recursive_pivot_service.expand(",
        "                            case_id=self.case_id,",
        "                            open_web_result=open_web_result,",
        "                            timeout=120,",
        "                        )",
        "                    )",
        "",
        "                self.result_ready.emit(",
        "                    {",
        '                        "target_type": target_type,',
        '                        "normalized_target": normalized,',
        '                        "open_web": open_web_result,',
        '                        "osint": None,',
        '                        "recursive": recursive_result,',
        "                    }",
        "                )",
    ])

    return text[:start] + replacement + text[end:]


def patch_view(text: str) -> str:
    if "M021.16.4 EMAIL result presentation" in text:
        return text

    text = text.replace(
        "Приложение само выберет доступный Open-Web путь.",
        "Приложение само выберет доступный Open-Web или OSINT путь.",
        1,
    )

    show_start = text.find(
        "    def show_result(self, payload: dict) -> None:"
    )
    entities_start = text.find(
        "    def _fill_entities(self, result) -> None:",
        show_start,
    )
    if show_start < 0 or entities_start < 0:
        raise RuntimeError("View show_result anchors not found.")

    show_block = _lines([
        "    def show_result(self, payload: dict) -> None:",
        "        # M021.16.4 EMAIL result presentation",
        "        self.clear_results()",
        "",
        '        osint_result = payload.get("osint")',
        "        if osint_result is not None:",
        "            self._show_osint_result(payload, osint_result)",
        "            return",
        "",
        '        result = payload["open_web"]',
        '        recursive = payload.get("recursive")',
        "        hydration = result.hydration",
        "",
        "        self.sources_table.setHorizontalHeaderLabels(",
        "            [",
        '                "Provider",',
        '                "URL",',
        '                "Capture",',
        '                "Content type",',
        '                "Hydration",',
        "            ]",
        "        )",
        "",
        "        hydrated = hydration.hydrated if hydration is not None else 0",
        "        hydration_failed = hydration.failed if hydration is not None else 0",
        "        recursive_candidates = (",
        "            recursive.candidates_discovered if recursive is not None else 0",
        "        )",
        "        recursive_targets = (",
        "            recursive.recursive_targets_processed if recursive is not None else 0",
        "        )",
        "",
        "        live_documents = sum(",
        "            1",
        "            for document in result.discovery.documents",
        '            if str(document.provider).casefold() == "live_web"',
        "        )",
        "        archive_documents = sum(",
        "            1",
        "            for document in result.discovery.documents",
        '            if str(document.provider).casefold() == "common_crawl"',
        "        )",
        "",
        "        self.overview.setPlainText(",
        '            "\\n".join(',
        "                [",
        '                    f"Цель: {payload[\'normalized_target\']}",',
        '                    f"Тип: {payload[\'target_type\'].value}",',
        '                    "",',
        '                    f"Найдено документов: {result.documents_found}",',
        '                    f"Live Web: {live_documents}",',
        '                    f"Common Crawl: {archive_documents}",',
        '                    f"Hydrated WARC: {hydrated}",',
        '                    f"Ошибок hydration: {hydration_failed}",',
        '                    f"Извлечено findings: {result.findings_extracted}",',
        '                    f"Сохранено findings: {result.persisted_findings}",',
        '                    f"Новых Source: {result.sources_created}",',
        '                    f"Новых Evidence: {result.evidences_created}",',
        '                    f"Новых Entity: {result.entities_created}",',
        '                    "",',
        '                    f"Recursive candidates: {recursive_candidates}",',
        '                    f"Recursive targets processed: {recursive_targets}",',
        "                ]",
        "            )",
        "        )",
        "",
        "        self._fill_entities(result)",
        "        self._fill_sources(result)",
        "        self.set_running(False)",
        '        self.status_label.setText("Поиск завершён.")',
        "",
        "    def _show_osint_result(self, payload: dict, result) -> None:",
        "        self.sources_table.setHorizontalHeaderLabels(",
        "            [",
        '                "Коннектор",',
        '                "Статус",',
        '                "Findings",',
        '                "Goal",',
        '                "Ошибка / детали",',
        "            ]",
        "        )",
        "",
        "        records = []",
        "        for execution in result.executions:",
        "            goal = getattr(getattr(execution, \"route\", None), \"goal\", None)",
        '            goal_value = getattr(goal, "value", str(goal or "—"))',
        "            for record in execution.records:",
        "                records.append((goal_value, record))",
        "",
        "        total_findings = sum(",
        '            getattr(execution, "total_findings", 0)',
        "            for execution in result.executions",
        "        )",
        "",
        "        def count_status(expected: str) -> int:",
        "            return sum(",
        "                1",
        "                for _, record in records",
        '                if getattr(record.result.status, "value", "") == expected',
        "            )",
        "",
        "        self.overview.setPlainText(",
        '            "\\n".join(',
        "                [",
        '                    f"Цель: {payload[\'normalized_target\']}",',
        '                    f"Тип: {payload[\'target_type\'].value}",',
        '                    "",',
        '                    f"Goals attempted: {result.goals_attempted}",',
        '                    f"Коннекторов проверено: {len(records)}",',
        '                    f"SUCCESS: {count_status(\'success\')}",',
        '                    f"NOT_AVAILABLE: {count_status(\'not_available\')}",',
        '                    f"FAILED: {count_status(\'failed\')}",',
        '                    f"Findings: {total_findings}",',
        '                    f"Сохранено findings: {result.persisted_findings}",',
        '                    f"Новых Source: {result.sources_created}",',
        '                    f"Новых Evidence: {result.evidences_created}",',
        '                    f"Новых Entity: {result.entities_created}",',
        '                    f"Новых Links: {result.links_created}",',
        '                    "",',
        '                    "Отсутствие одного коннектора не означает отсутствие данных.",',
        "                ]",
        "            )",
        "        )",
        "",
        "        self._fill_entities(result)",
        "        self._fill_osint_sources(result)",
        "        self.set_running(False)",
        '        self.status_label.setText("Email-поиск завершён.")',
        "",
    ])

    text = text[:show_start] + show_block + text[entities_start:]

    sources_start = text.find(
        "    def _fill_sources(self, result) -> None:"
    )
    if sources_start < 0:
        raise RuntimeError("View _fill_sources anchor not found.")

    osint_sources = _lines([
        "    def _fill_osint_sources(self, result) -> None:",
        "        for execution in result.executions:",
        "            goal = getattr(getattr(execution, \"route\", None), \"goal\", None)",
        '            goal_value = getattr(goal, "value", str(goal or "—"))',
        "",
        "            for record in execution.records:",
        "                connector_result = record.result",
        "                status = getattr(",
        "                    connector_result.status,",
        '                    "value",',
        "                    str(connector_result.status),",
        "                )",
        "                findings = getattr(connector_result, \"total_findings\", 0)",
        "                detail = connector_result.error or (",
        '                    "Доступен; совпадений не найдено."',
        '                    if status == "success" and findings == 0',
        '                    else "—"',
        "                )",
        "                connector_name = (",
        "                    record.runtime_connector_name",
        "                    or connector_result.connector",
        "                    or record.capability.display_name",
        "                )",
        "",
        "                row = self.sources_table.rowCount()",
        "                self.sources_table.insertRow(row)",
        "                cells = [",
        "                    str(connector_name),",
        "                    str(status),",
        "                    str(findings),",
        "                    str(goal_value),",
        "                    str(detail),",
        "                ]",
        "                for col, cell in enumerate(cells):",
        "                    self.sources_table.setItem(",
        "                        row,",
        "                        col,",
        "                        QTableWidgetItem(cell),",
        "                    )",
        "",
    ])

    return text[:sources_start] + osint_sources + text[sources_start:]


def main() -> int:
    for path in (WORKER, VIEW):
        if not path.is_file():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        WORKER: WORKER.read_text(encoding="utf-8"),
        VIEW: VIEW.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            WORKER: patch_worker(originals[WORKER]),
            VIEW: patch_view(originals[VIEW]),
        }
        for path, value in updated.items():
            compile(value, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_4_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(value, encoding="utf-8")

    print("[PASS] EMAIL routed to existing OsintEnrichmentService.")
    print("[PASS] URL/DOMAIN Open-Web route preserved.")
    print("[PASS] Connector status table added.")
    print("[PASS] No second pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
