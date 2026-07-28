"""
Report workspace view.

Responsible for:

- displaying investigation reports

Does NOT:

- access database
- generate reports
- execute business logic
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QTextEdit,
)



class ReportWorkspaceView(QWidget):
    """
    Reports workspace UI.
    """



    def __init__(
        self,
    ):

        super().__init__()


        self._setup_ui()



    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create reports interface.
        """


        layout = QVBoxLayout(
            self
        )


        self.title = QLabel(
            "Investigation Reports"
        )


        layout.addWidget(
            self.title
        )



        self.report_list = QListWidget()


        self.report_list.itemClicked.connect(
            self._select_report
        )


        layout.addWidget(
            self.report_list
        )



        self.content = QTextEdit()


        self.content.setReadOnly(
            True
        )


        layout.addWidget(
            self.content
        )



        self.reports = []



    # ==========================================================
    # Data
    # ==========================================================

    def set_reports(
        self,
        reports: list,
    ) -> None:
        """
        Load reports.
        """


        self.reports = reports


        self.report_list.clear()


        for report in reports:

            self.report_list.addItem(
                report.get(
                    "title",
                    "Report"
                )
            )



    # ==========================================================
    # Selection
    # ==========================================================

    def _select_report(
        self,
        item,
    ) -> None:
        """
        Display selected report.
        """


        index = (
            self.report_list
            .row(item)
        )


        if index >= len(
            self.reports
        ):
            return



        report = (
            self.reports[index]
        )


        self.content.setText(

            report.get(
                "content",
                ""
            )

        )