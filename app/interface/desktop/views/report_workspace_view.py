"""
Report workspace view.

Responsible for:

- displaying investigation reports
- selecting reports
- rendering Markdown content
- copying report content
- saving report content to a Markdown file
- reacting to application language changes

Does NOT:

- access database
- generate reports
- execute business logic
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtGui import (
    QGuiApplication,
)

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class ReportWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Reports workspace UI.

    The view automatically updates all visible interface text
    when the active application language changes.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self.reports: list[
            dict[str, Any]
        ] = []

        self.selected_report: (
            dict[str, Any] | None
        ) = None

        self._setup_ui()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._show_empty_state()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create reports interface.
        """

        self.setObjectName(
            "ReportWorkspaceView"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        self.main_layout.setSpacing(
            10
        )

        self._create_header()
        self._create_workspace()

    def _create_header(
        self,
    ) -> None:
        """
        Create reports workspace header.
        """

        self.header_layout = QHBoxLayout()

        self.title_label = QLabel(
            "Investigation Reports",
            self,
        )

        self.title_label.setObjectName(
            "ReportWorkspaceTitle"
        )

        title_font = (
            self.title_label.font()
        )

        title_font.setBold(
            True
        )

        title_font.setPointSize(
            title_font.pointSize() + 2
        )

        self.title_label.setFont(
            title_font
        )

        self.report_count_label = QLabel(
            "Reports: 0",
            self,
        )

        self.report_count_label.setObjectName(
            "ReportWorkspaceCount"
        )

        self.report_count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.header_layout.addWidget(
            self.title_label
        )

        self.header_layout.addStretch()

        self.header_layout.addWidget(
            self.report_count_label
        )

        self.main_layout.addLayout(
            self.header_layout
        )

    def _create_workspace(
        self,
    ) -> None:
        """
        Create split report workspace.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.splitter.setObjectName(
            "ReportWorkspaceSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_report_list_panel()
        self._create_report_content_panel()

        self.splitter.setStretchFactor(
            0,
            1,
        )

        self.splitter.setStretchFactor(
            1,
            3,
        )

        self.splitter.setSizes(
            [
                280,
                850,
            ]
        )

        self.main_layout.addWidget(
            self.splitter,
            1,
        )

    def _create_report_list_panel(
        self,
    ) -> None:
        """
        Create available reports list panel.
        """

        self.list_panel = QWidget(
            self.splitter
        )

        self.list_panel.setObjectName(
            "ReportListPanel"
        )

        self.list_layout = QVBoxLayout(
            self.list_panel
        )

        self.list_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.list_layout.setSpacing(
            6
        )

        self.list_title_label = QLabel(
            "Available reports",
            self.list_panel,
        )

        self.list_title_label.setObjectName(
            "ReportListTitle"
        )

        list_title_font = (
            self.list_title_label.font()
        )

        list_title_font.setBold(
            True
        )

        self.list_title_label.setFont(
            list_title_font
        )

        self.list_layout.addWidget(
            self.list_title_label
        )

        self.report_list = QListWidget(
            self.list_panel
        )

        self.report_list.setObjectName(
            "ReportList"
        )

        self.report_list.setAlternatingRowColors(
            True
        )

        self.report_list.setWordWrap(
            True
        )

        self.report_list.currentRowChanged.connect(
            self._select_report_by_index
        )

        self.list_layout.addWidget(
            self.report_list,
            1,
        )

        self.splitter.addWidget(
            self.list_panel
        )

    def _create_report_content_panel(
        self,
    ) -> None:
        """
        Create selected report content panel.
        """

        self.content_panel = QWidget(
            self.splitter
        )

        self.content_panel.setObjectName(
            "ReportContentPanel"
        )

        self.content_layout = QVBoxLayout(
            self.content_panel
        )

        self.content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.content_layout.setSpacing(
            8
        )

        self.report_title_label = QLabel(
            "No report selected",
            self.content_panel,
        )

        self.report_title_label.setObjectName(
            "SelectedReportTitle"
        )

        report_title_font = (
            self.report_title_label.font()
        )

        report_title_font.setBold(
            True
        )

        report_title_font.setPointSize(
            report_title_font.pointSize() + 1
        )

        self.report_title_label.setFont(
            report_title_font
        )

        self.report_title_label.setWordWrap(
            True
        )

        self.content_layout.addWidget(
            self.report_title_label
        )

        self.report_type_label = QLabel(
            "",
            self.content_panel,
        )

        self.report_type_label.setObjectName(
            "SelectedReportType"
        )

        self.report_type_label.setWordWrap(
            True
        )

        self.content_layout.addWidget(
            self.report_type_label
        )

        self._create_action_buttons()

        self.content = QTextBrowser(
            self.content_panel
        )

        self.content.setObjectName(
            "ReportMarkdownViewer"
        )

        self.content.setOpenExternalLinks(
            False
        )

        self.content.setReadOnly(
            True
        )

        self.content_layout.addWidget(
            self.content,
            1,
        )

        self.splitter.addWidget(
            self.content_panel
        )

    def _create_action_buttons(
        self,
    ) -> None:
        """
        Create report action buttons.
        """

        self.action_layout = QHBoxLayout()

        self.copy_button = QPushButton(
            "Copy",
            self.content_panel,
        )

        self.copy_button.setObjectName(
            "CopyReportButton"
        )

        self.save_button = QPushButton(
            "Save as Markdown",
            self.content_panel,
        )

        self.save_button.setObjectName(
            "SaveReportButton"
        )

        self.copy_button.clicked.connect(
            self._copy_report
        )

        self.save_button.clicked.connect(
            self._save_report
        )

        self.action_layout.addWidget(
            self.copy_button
        )

        self.action_layout.addWidget(
            self.save_button
        )

        self.action_layout.addStretch()

        self.content_layout.addLayout(
            self.action_layout
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        self.title_label.setText(
            self.translate(
                "report.section.title",
                default="Investigation Reports",
            )
        )

        self.list_title_label.setText(
            self.translate(
                "report.list.title",
                default="Available reports",
            )
        )

        self.copy_button.setText(
            self.translate(
                "report.action.copy",
                default="Copy",
            )
        )

        self.save_button.setText(
            self.translate(
                "report.action.save_markdown",
                default="Save as Markdown",
            )
        )

        self._update_report_count()

        selected_report_id = None

        if self.selected_report is not None:

            selected_report_id = (
                self.selected_report.get(
                    "id"
                )
            )

        self._populate_report_list(
            selected_report_id=selected_report_id
        )

        if self.selected_report is None:

            self._show_empty_state()

            return

        self._refresh_selected_report()

            # ==========================================================
    # Data
    # ==========================================================

    def set_reports(
        self,
        reports: list[dict[str, Any]],
    ) -> None:
        """
        Load reports into workspace.
        """

        selected_report_id = None

        if self.selected_report is not None:

            selected_report_id = (
                self.selected_report.get(
                    "id"
                )
            )

        self.reports = list(
            reports or []
        )

        self.selected_report = None

        self._populate_report_list(
            selected_report_id
        )

        self._update_report_count()

        if not self.reports:

            self._show_empty_state()

            return

        if self.report_list.currentRow() < 0:

            self.report_list.setCurrentRow(
                0
            )

    def _populate_report_list(
        self,
        selected_report_id: Any = None,
    ) -> None:
        """
        Populate report list.
        """

        self.report_list.blockSignals(
            True
        )

        self.report_list.clear()

        selected_index = -1

        untitled = self.translate(
            "report.item.untitled",
            default="Untitled report",
        )

        for index, report in enumerate(
            self.reports
        ):

            title = str(
                report.get(
                    "title"
                )
                or untitled
            )

            report_type = (
                self._format_report_type(
                    report.get(
                        "type",
                        "OTHER",
                    )
                )
            )

            item = QListWidgetItem(
                f"{title}\n{report_type}"
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                report.get(
                    "id"
                ),
            )

            item.setToolTip(
                (
                    f"{self.translate('report.tooltip.title', default='Title')}: {title}\n"
                    f"{self.translate('report.tooltip.type', default='Type')}: {report_type}"
                )
            )

            self.report_list.addItem(
                item
            )

            if (
                selected_report_id is not None
                and str(
                    report.get("id")
                )
                == str(
                    selected_report_id
                )
            ):
                selected_index = index

        self.report_list.blockSignals(
            False
        )

        if selected_index >= 0:

            self.report_list.setCurrentRow(
                selected_index
            )

    def _update_report_count(
        self,
    ) -> None:
        """
        Update report counter.
        """

        self.report_count_label.setText(
            self.translate(
                "report.count",
                default="Reports: {count}",
                count=len(self.reports),
            )
        )

    # ==========================================================
    # Selection
    # ==========================================================

    def _select_report_by_index(
        self,
        index: int,
    ) -> None:

        if (
            index < 0
            or index >= len(
                self.reports
            )
        ):

            self._show_empty_state()

            return

        self.selected_report = (
            self.reports[index]
        )

        self._refresh_selected_report()

    def _refresh_selected_report(
        self,
    ) -> None:
        """
        Refresh currently selected report.
        """

        if self.selected_report is None:

            self._show_empty_state()

            return

        untitled = self.translate(
            "report.item.untitled",
            default="Untitled report",
        )

        title = str(
            self.selected_report.get(
                "title"
            )
            or untitled
        )

        report_type = (
            self._format_report_type(
                self.selected_report.get(
                    "type",
                    "OTHER",
                )
            )
        )

        content = str(
            self.selected_report.get(
                "content",
                "",
            )
            or ""
        )

        self.report_title_label.setText(
            title
        )

        self.report_type_label.setText(
            self.translate(
                "report.type",
                default="Report type: {type}",
                type=report_type,
            )
        )

        if content.strip():

            self.content.setMarkdown(
                content
            )

        else:

            self.content.setPlainText(
                self.translate(
                    "report.empty_content",
                    default="This report has no content.",
                )
            )

        enabled = bool(
            content.strip()
        )

        self.copy_button.setEnabled(
            enabled
        )

        self.save_button.setEnabled(
            enabled
        )

    # ==========================================================
    # Actions
    # ==========================================================

    def _copy_report(
        self,
    ) -> None:

        if self.selected_report is None:
            return

        content = str(
            self.selected_report.get(
                "content",
                "",
            )
            or ""
        )

        if not content:
            return

        QGuiApplication.clipboard().setText(
            content
        )

        QMessageBox.information(
            self,
            self.translate(
                "report.copy.title",
                default="Report copied",
            ),
            self.translate(
                "report.copy.message",
                default=(
                    "The report content was copied "
                    "to the clipboard."
                ),
            ),
        )

    def _save_report(
        self,
    ) -> None:

        if self.selected_report is None:
            return

        title = str(
            self.selected_report.get(
                "title",
                "investigation_report",
            )
        )

        content = str(
            self.selected_report.get(
                "content",
                "",
            )
            or ""
        )

        if not content:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.translate(
                "report.save.dialog_title",
                default="Save investigation report",
            ),
            self._build_file_name(
                title
            ),
            self.translate(
                "report.save.filter",
                default=(
                    "Markdown files (*.md);;"
                    "Text files (*.txt);;"
                    "All files (*)"
                ),
            ),
        )

        if not file_path:
            return

        if not (
            file_path.lower().endswith(".md")
            or file_path.lower().endswith(".txt")
        ):
            file_path += ".md"

        try:

            with open(
                file_path,
                "w",
                encoding="utf-8",
            ) as file:

                file.write(
                    content
                )

            QMessageBox.information(
                self,
                self.translate(
                    "report.save.success.title",
                    default="Report saved",
                ),
                self.translate(
                    "report.save.success.message",
                    default="The report was saved successfully.",
                ),
            )

        except OSError as exc:

            QMessageBox.critical(
                self,
                self.translate(
                    "report.save.error.title",
                    default="Save failed",
                ),
                self.translate(
                    "report.save.error.message",
                    default=(
                        "The report could not be saved.\n\n{error}"
                    ),
                    error=str(exc),
                ),
            )

    # ==========================================================
    # State
    # ==========================================================

    def _show_empty_state(
        self,
    ) -> None:

        self.selected_report = None

        self.report_title_label.setText(
            self.translate(
                "report.no_selection",
                default="No report selected",
            )
        )

        self.report_type_label.clear()

        if self.reports:

            message = self.translate(
                "report.empty.select",
                default=(
                    "Select a report from the list "
                    "to view its content."
                ),
            )

        else:

            message = self.translate(
                "report.empty.workspace",
                default=(
                    "No investigation reports are available.\n\n"
                    "Import investigation data to generate "
                    "a summary report."
                ),
            )

        self.content.setPlainText(
            message
        )

        self.copy_button.setEnabled(
            False
        )

        self.save_button.setEnabled(
            False
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _format_report_type(
        self,
        report_type: Any,
    ) -> str:

        value = str(
            report_type or "OTHER"
        )

        return (
            value.replace(
                "_",
                " ",
            )
            .strip()
            .title()
        )

    def _build_file_name(
        self,
        title: str,
    ) -> str:

        invalid = '<>:"/\\|?*'

        safe = "".join(
            "_"
            if ch in invalid
            else ch
            for ch in title
        )

        safe = (
            safe.strip()
            .replace(
                " ",
                "_",
            )
        )

        if not safe:

            safe = "investigation_report"

        return f"{safe}.md"