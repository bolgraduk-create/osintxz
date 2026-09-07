from __future__ import annotations
from app.registry_intelligence.query_detection import detect_registry_query

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.workers.investigation_search_worker import (
    detect_investigation_target,
)


class InvestigationSearchView(QWidget):
    search_requested = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("InvestigationSearchView")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Investigation Search", self)
        title.setObjectName("InvestigationSearchTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Введите URL, домен, email, телефон или username. "
            "Приложение само выберет доступный Open-Web или OSINT путь.",
            self,
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        self.target_input = QLineEdit(self)
        self.target_input.setPlaceholderText(
            "URL / IP / email / phone / username / company name / LEI"
        )
        self.target_input.textChanged.connect(self._update_detected_type)
        self.target_input.returnPressed.connect(self._emit_search)
        search_row.addWidget(self.target_input, 1)

        self.search_button = QPushButton("Поиск", self)
        self.search_button.setProperty("variant", "primary")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(self._emit_search)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        options = QHBoxLayout()
        self.detected_type_label = QLabel("Тип: —", self)
        options.addWidget(self.detected_type_label)
        options.addStretch(1)

        self.recursive_checkbox = QCheckBox(
            "Автоматически продолжать поиск по найденным сущностям",
            self,
        )
        self.recursive_checkbox.setChecked(False)
        options.addWidget(self.recursive_checkbox)
        layout.addLayout(options)

        self.status_label = QLabel("Готово к поиску.", self)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.results_tabs = QTabWidget(self)

        self.overview = QTextBrowser(self.results_tabs)
        self.results_tabs.addTab(self.overview, "Обзор")

        self.entities_table = QTableWidget(0, 5, self.results_tabs)
        self.entities_table.setHorizontalHeaderLabels(
            ["Тип", "Значение", "Confidence", "Источник", "Evidence"]
        )
        self.entities_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.entities_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.results_tabs.addTab(self.entities_table, "Сущности")

        self.sources_table = QTableWidget(0, 5, self.results_tabs)
        self.sources_table.setHorizontalHeaderLabels(
            ["Provider", "URL", "Capture", "Content type", "Hydration"]
        )
        self.sources_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.sources_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.results_tabs.addTab(self.sources_table, "Источники")

        layout.addWidget(self.results_tabs, 1)

    def _emit_search(self) -> None:
        target = self.target_input.text().strip()
        if not target:
            self.status_label.setText("Введите цель поиска.")
            return

        try:
            if detect_registry_query(target) is None:
                detect_investigation_target(target)
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return

        self.search_requested.emit(
            target,
            self.recursive_checkbox.isChecked(),
        )

    def _update_detected_type(self, value: str) -> None:
        if not value.strip():
            self.detected_type_label.setText("Тип: —")
            return
        try:
            registry_query = detect_registry_query(value)
            if registry_query is not None:
                self.detected_type_label.setText(f"Registry: {registry_query.kind.value}")
                return
            target_type, _ = detect_investigation_target(value)
        except ValueError:
            self.detected_type_label.setText("Тип: не определён")
            return
        self.detected_type_label.setText(
            f"Тип: {target_type.value.upper()}"
        )

    def set_running(self, running: bool) -> None:
        self.target_input.setEnabled(not running)
        self.search_button.setEnabled(not running)
        self.recursive_checkbox.setEnabled(not running)
        if running:
            self.progress.setRange(0, 0)
            self.status_label.setText("Выполняется поиск...")
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def clear_results(self) -> None:
        self.overview.clear()
        self.entities_table.setRowCount(0)
        self.sources_table.setRowCount(0)

    def show_error(self, text: str) -> None:
        self.set_running(False)
        self.status_label.setText(f"Ошибка: {text}")
        self.overview.setPlainText(text)

    def show_result(self, payload: dict) -> None:
        if payload.get("registry") is not None:
            self._show_registry_result(payload["registry"])
            return
        # M021.16.4 EMAIL result presentation
        self.clear_results()

        osint_result = payload.get("osint")
        if osint_result is not None:
            # M021.16.5.2A combined EMAIL OSINT/Open-Web presentation
            self._show_osint_result(
                payload,
                osint_result,
                payload.get("open_web"),
            )
            return

        result = payload["open_web"]
        recursive = payload.get("recursive")
        hydration = result.hydration

        self.sources_table.setHorizontalHeaderLabels(
            [
                "Provider",
                "URL",
                "Capture",
                "Content type",
                "Hydration",
            ]
        )

        hydrated = hydration.hydrated if hydration is not None else 0
        hydration_failed = hydration.failed if hydration is not None else 0
        recursive_candidates = (
            recursive.candidates_discovered if recursive is not None else 0
        )
        recursive_targets = (
            recursive.recursive_targets_processed if recursive is not None else 0
        )

        live_documents = sum(
            1
            for document in result.discovery.documents
            if str(document.provider).casefold() == "live_web"
        )
        archive_documents = sum(
            1
            for document in result.discovery.documents
            if str(document.provider).casefold() == "common_crawl"
        )

        self.overview.setPlainText(
            "\n".join(
                [
                    f"Цель: {payload['normalized_target']}",
                    f"Тип: {payload['target_type'].value}",
                    "",
                    f"Найдено документов: {result.documents_found}",
                    f"Live Web: {live_documents}",
                    f"Common Crawl: {archive_documents}",
                    f"Hydrated WARC: {hydrated}",
                    f"Ошибок hydration: {hydration_failed}",
                    f"Извлечено findings: {result.findings_extracted}",
                    f"Сохранено findings: {result.persisted_findings}",
                    f"Новых Source: {result.sources_created}",
                    f"Новых Evidence: {result.evidences_created}",
                    f"Новых Entity: {result.entities_created}",
                    "",
                    f"Recursive candidates: {recursive_candidates}",
                    f"Recursive targets processed: {recursive_targets}",
                ]
            )
        )

        self._fill_entities(result)
        self._fill_sources(result)
        self.set_running(False)
        self.status_label.setText("Поиск завершён.")

    def _show_registry_result(self, result) -> None:
        self.clear_results()
        persisted = result.persistence
        self.sources_table.setHorizontalHeaderLabels(["Provider", "Status", "Records", "Goal", "Detail"])
        self.overview.setPlainText("\n".join([
            f"Registry query: {result.search.query.value}",
            f"Records: {len(result.search.records)}; persisted: {len(persisted.records)}",
            f"New sources: {persisted.sources_created}; evidence: {persisted.evidences_created}",
            f"New entities: {persisted.entities_created}; links: {persisted.links_created}",
            "Organization fusion uses exact registry identifiers, never name alone.",
            "Name search results are registry records; they do not establish personal identity or ownership.",
            *persisted.errors,
        ]))
        for provider in result.search.provider_results:
            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)
            status = "rate_limited" if provider.metadata.get("rate_limited") else provider.status.value
            for column, cell in enumerate([provider.provider, status, len(provider.records),
                    f"registry_{result.search.query.kind.value}", (provider.error or "")[:300]]):
                self.sources_table.setItem(row, column, QTableWidgetItem(str(cell)))
        grouped = {}
        for record in persisted.records:
            for entity in record.entities:
                item = grouped.setdefault(entity.id, [entity, set(), set()])
                item[1].add(record.source.name)
                item[2].add(str(record.evidence.id))
        for entity, sources, evidences in grouped.values():
            row = self.entities_table.rowCount()
            self.entities_table.insertRow(row)
            for column, cell in enumerate([entity.entity_type.value, entity.value,
                    f"{entity.confidence:.2f}", ", ".join(sorted(sources)), ", ".join(sorted(evidences))]):
                self.entities_table.setItem(row, column, QTableWidgetItem(str(cell)))
        self.set_running(False)
        self.status_label.setText("Registry search completed.")

    def _show_osint_result(
        self,
        payload: dict,
        result,
        open_web_result=None,
    ) -> None:
        self.sources_table.setHorizontalHeaderLabels(
            [
                "Коннектор",
                "Статус",
                "Findings",
                "Goal",
                "Ошибка / детали",
            ]
        )

        records = []
        for execution in result.executions:
            goal = getattr(getattr(execution, "route", None), "goal", None)
            goal_value = getattr(goal, "value", str(goal or "—"))
            for record in execution.records:
                records.append((goal_value, record))

        total_findings = sum(
            getattr(execution, "total_findings", 0)
            for execution in result.executions
        )

        public_documents = (
            open_web_result.documents_found
            if open_web_result is not None
            else 0
        )
        public_findings = (
            open_web_result.findings_extracted
            if open_web_result is not None
            else 0
        )
        public_persisted = (
            open_web_result.persisted_findings
            if open_web_result is not None
            else 0
        )

        def count_status(expected: str) -> int:
            return sum(
                1
                for _, record in records
                if getattr(record.result.status, "value", "") == expected
            )

        self.overview.setPlainText(
            "\n".join(
                [
                    f"Цель: {payload['normalized_target']}",
                    f"Тип: {payload['target_type'].value}",
                    "",
                    f"Goals attempted: {result.goals_attempted}",
                    f"Коннекторов проверено: {len(records)}",
                    f"SUCCESS: {count_status('success')}",
                    f"NOT_AVAILABLE: {count_status('not_available')}",
                    f"FAILED: {count_status('failed')}",
                    f"OSINT findings: {total_findings}",
                    f"OSINT сохранено: {result.persisted_findings}",
                    "",
                    f"Public-Web подтверждённых страниц: {public_documents}",
                    f"Public-Web findings: {public_findings}",
                    f"Public-Web сохранено: {public_persisted}",
                    f"Новых Source: {result.sources_created}",
                    f"Новых Evidence: {result.evidences_created}",
                    f"Новых Entity: {result.entities_created}",
                    f"Новых Links: {result.links_created}",
                    "",
                    "Отсутствие одного коннектора не означает отсутствие данных.",
                ]
            )
        )

        if open_web_result is None:
            self._fill_entities(result)
        else:
            class _CombinedPersistence:
                pass

            combined = _CombinedPersistence()
            combined.persistence = (
                list(result.persistence)
                + list(open_web_result.persistence)
            )
            self._fill_entities(combined)

        self._fill_osint_sources(result)

        if open_web_result is not None:
            self._fill_email_open_web_sources(
                open_web_result
            )

        # M021.16.6.2 generic OSINT result status
        self.set_running(False)
        target_type = payload.get("target_type")
        target_value = getattr(target_type, "value", str(target_type or "OSINT"))
        self.status_label.setText(
            f"OSINT-поиск ({target_value}) завершён."
        )

    def _fill_entities(self, result) -> None:
        # M021.16.3.3 unique entity presentation
        grouped = {}

        for persistence in result.persistence:
            for persisted in persistence.persisted:
                evidence = getattr(persisted, "evidence", None)
                evidence_id = getattr(evidence, "id", None)

                for entity in persisted.entities:
                    entity_type = getattr(entity, "entity_type", "")
                    type_value = getattr(
                        entity_type,
                        "value",
                        str(entity_type),
                    )
                    value = (
                        getattr(entity, "normalized_value", None)
                        or getattr(entity, "value", "")
                    )

                    key = (
                        str(type_value).casefold(),
                        str(value).casefold(),
                    )

                    confidence = getattr(entity, "confidence", None)
                    confidence_value = (
                        float(confidence)
                        if isinstance(confidence, (int, float))
                        else None
                    )

                    item = grouped.setdefault(
                        key,
                        {
                            "type": str(type_value),
                            "value": str(value),
                            "confidence": confidence_value,
                            "sources": set(),
                            "evidence_ids": set(),
                        },
                    )

                    if (
                        confidence_value is not None
                        and (
                            item["confidence"] is None
                            or confidence_value > item["confidence"]
                        )
                    ):
                        item["confidence"] = confidence_value

                    target_value = getattr(
                        persistence,
                        "target_value",
                        None,
                    )
                    if target_value:
                        item["sources"].add(str(target_value))

                    if evidence_id is not None:
                        item["evidence_ids"].add(str(evidence_id))

        for item in sorted(
            grouped.values(),
            key=lambda value: (
                value["type"].casefold(),
                value["value"].casefold(),
            ),
        ):
            confidence_text = (
                f"{item['confidence']:.2f}"
                if item["confidence"] is not None
                else "—"
            )

            evidence_ids = sorted(item["evidence_ids"])
            evidence_text = (
                evidence_ids[0]
                if len(evidence_ids) == 1
                else (
                    f"{len(evidence_ids)} evidence"
                    if evidence_ids
                    else "—"
                )
            )

            source_text = ", ".join(
                sorted(item["sources"])
            ) or "—"

            row = self.entities_table.rowCount()
            self.entities_table.insertRow(row)

            cells = [
                item["type"],
                item["value"],
                confidence_text,
                source_text,
                evidence_text,
            ]

            for col, cell in enumerate(cells):
                self.entities_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(cell)),
                )

    def _fill_email_open_web_sources(
        self,
        result,
    ) -> None:
        for provider_result in result.discovery.results:
            metadata = provider_result.metadata or {}
            documents = len(provider_result.documents)

            detail_parts = []

            candidates = metadata.get("candidates_returned")
            verified = metadata.get("verified_documents")

            if candidates is not None:
                detail_parts.append(
                    f"кандидатов: {candidates}"
                )

            if verified is not None:
                detail_parts.append(
                    f"подтверждено: {verified}"
                )

            if provider_result.error:
                detail_parts.append(provider_result.error)

            detail = (
                "; ".join(detail_parts)
                or (
                    "Доступен; точных публичных "
                    "упоминаний не найдено."
                    if documents == 0
                    else "—"
                )
            )

            status = getattr(
                provider_result.status,
                "value",
                str(provider_result.status),
            )

            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)

            cells = [
                str(provider_result.provider),
                str(status),
                str(documents),
                # M021.16.7.10 OPEN-WEB GOAL LABEL
                "open_web_discovery",
                str(detail),
            ]

            for col, cell in enumerate(cells):
                self.sources_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(cell),
                )

    def _fill_osint_sources(self, result) -> None:
        for execution in result.executions:
            goal = getattr(getattr(execution, "route", None), "goal", None)
            goal_value = getattr(goal, "value", str(goal or "—"))

            for record in execution.records:
                connector_result = record.result
                status = getattr(
                    connector_result.status,
                    "value",
                    str(connector_result.status),
                )
                findings = getattr(connector_result, "total_findings", 0)
                detail = connector_result.error or (
                    "Доступен; совпадений не найдено."
                    if status == "success" and findings == 0
                    else "—"
                )
                connector_name = (
                    record.runtime_connector_name
                    or connector_result.connector
                    or record.capability.display_name
                )

                row = self.sources_table.rowCount()
                self.sources_table.insertRow(row)
                cells = [
                    str(connector_name),
                    str(status),
                    str(findings),
                    str(goal_value),
                    str(detail),
                ]
                for col, cell in enumerate(cells):
                    self.sources_table.setItem(
                        row,
                        col,
                        QTableWidgetItem(cell),
                    )

    def _fill_sources(self, result) -> None:
        hydration_by_url = {}
        if result.hydration is not None:
            for document in result.hydration.documents:
                meta = document.metadata.get("content_hydration", {})
                hydration_by_url[document.url] = meta.get("status", "—")

        for document in result.discovery.documents:
            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)
            captured_at = getattr(document, "captured_at", None)
            cells = [
                str(document.provider),
                str(document.url),
                str(captured_at or "—"),
                str(document.content_type or "—"),
                str(hydration_by_url.get(document.url, "—")),
            ]
            for col, cell in enumerate(cells):
                self.sources_table.setItem(
                    row, col, QTableWidgetItem(cell)
                )
