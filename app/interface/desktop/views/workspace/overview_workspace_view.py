"""
Overview workspace view.

Responsible for:

- displaying investigation summary
- displaying case statistics
- displaying general information

Does NOT:

- access database
- execute business logic
- perform analysis
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
)


class OverviewWorkspaceView(QWidget):
    """
    Investigation overview.
    """

    def __init__(
        self,
    ) -> None:

        super().__init__()

        self._setup_ui()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        layout = QVBoxLayout(
            self
        )

        self.title = QLabel()

        self.title.setStyleSheet(
            """
            font-size:24px;
            font-weight:bold;
            """
        )

        layout.addWidget(
            self.title
        )

        self.description = QLabel()

        self.description.setWordWrap(
            True
        )

        layout.addWidget(
            self.description
        )

        self.statistics = QLabel()

        self.statistics.setWordWrap(
            True
        )

        layout.addWidget(
            self.statistics
        )

        layout.addStretch()

    # ==========================================================
    # Update
    # ==========================================================

    def set_overview(
        self,
        case_data: dict,
        statistics: dict,
    ) -> None:
        """
        Update overview.
        """

        self.title.setText(
            case_data.get(
                "title",
                "",
            )
        )

        self.description.setText(
            case_data.get(
                "description",
                "",
            )
        )

        self.statistics.setText(
            (
                f"Evidence: {statistics.get('evidence', 0)}\n"
                f"Entities: {statistics.get('entities', 0)}\n"
                f"Relationships: {statistics.get('relationships', 0)}\n"
                f"Reports: {statistics.get('reports', 0)}\n"
                f"Timeline: {statistics.get('timeline', 0)}"
            )
        )