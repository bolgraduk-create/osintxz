"""
AI result dialog.

Displays a saved AI analysis result.

Responsible for:

- showing model and analysis metadata
- displaying AI-generated content
- copying analysis text
- exposing the stored analysis identifier

Does NOT:

- call AI providers
- save analysis records
- access repositories
- contain investigation business logic
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import (
    Qt,
)

from PySide6.QtGui import (
    QGuiApplication,
)

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AIResultDialog(
    QDialog,
):
    """
    Dialog for displaying one AI analysis result.
    """

    def __init__(
        self,
        analysis: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        if not isinstance(
            analysis,
            dict,
        ):

            raise TypeError(
                "analysis must be a dictionary."
            )

        self.analysis = dict(
            analysis
        )

        self.setObjectName(
            "AIResultDialog"
        )

        self.setWindowTitle(
            "AI Investigation Analysis"
        )

        self.setModal(
            True
        )

        self.resize(
            900,
            700,
        )

        self.setMinimumSize(
            720,
            520,
        )

        self._setup_ui()
        self._load_analysis()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.main_layout.setSpacing(
            14
        )

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        self.header_frame = QFrame(
            self
        )

        self.header_frame.setObjectName(
            "AIResultHeader"
        )

        self.header_layout = QVBoxLayout(
            self.header_frame
        )

        self.header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.header_layout.setSpacing(
            6
        )

        self.title_label = QLabel(
            "AI Investigation Analysis",
            self.header_frame,
        )

        self.title_label.setObjectName(
            "AIResultTitle"
        )

        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.subtitle_label = QLabel(
            "Review the generated analysis and its execution metadata.",
            self.header_frame,
        )

        self.subtitle_label.setObjectName(
            "AIResultSubtitle"
        )

        self.subtitle_label.setWordWrap(
            True
        )

        self.header_layout.addWidget(
            self.title_label
        )

        self.header_layout.addWidget(
            self.subtitle_label
        )

        self.main_layout.addWidget(
            self.header_frame
        )

        # ------------------------------------------------------
        # Metadata
        # ------------------------------------------------------

        self.metadata_frame = QFrame(
            self
        )

        self.metadata_frame.setObjectName(
            "AIResultMetadata"
        )

        self.metadata_layout = QHBoxLayout(
            self.metadata_frame
        )

        self.metadata_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )

        self.metadata_layout.setSpacing(
            18
        )

        self.model_label = QLabel(
            self.metadata_frame
        )

        self.type_label = QLabel(
            self.metadata_frame
        )

        self.created_label = QLabel(
            self.metadata_frame
        )

        self.context_label = QLabel(
            self.metadata_frame
        )

        for label in (
            self.model_label,
            self.type_label,
            self.created_label,
            self.context_label,
        ):

            label.setObjectName(
                "AIResultMetadataLabel"
            )

            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            self.metadata_layout.addWidget(
                label
            )

        self.metadata_layout.addStretch(
            1
        )

        self.main_layout.addWidget(
            self.metadata_frame
        )

        # ------------------------------------------------------
        # Result
        # ------------------------------------------------------

        self.result_label = QLabel(
            "Analysis",
            self,
        )

        self.result_label.setObjectName(
            "AIResultSectionTitle"
        )

        self.main_layout.addWidget(
            self.result_label
        )

        self.result_text = QTextEdit(
            self
        )

        self.result_text.setObjectName(
            "AIResultText"
        )

        self.result_text.setReadOnly(
            True
        )

        self.result_text.setAcceptRichText(
            False
        )

        self.result_text.setLineWrapMode(
            QTextEdit.LineWrapMode.WidgetWidth
        )

        self.result_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.main_layout.addWidget(
            self.result_text,
            1,
        )

        # ------------------------------------------------------
        # Buttons
        # ------------------------------------------------------

        self.button_box = QDialogButtonBox(
            self
        )

        self.copy_button = QPushButton(
            "Copy",
            self.button_box,
        )

        self.copy_button.setObjectName(
            "AIResultCopyButton"
        )

        self.details_button = QPushButton(
            "Show details",
            self.button_box,
        )

        self.details_button.setObjectName(
            "AIResultDetailsButton"
        )

        self.close_button = QPushButton(
            "Close",
            self.button_box,
        )

        self.close_button.setObjectName(
            "AIResultCloseButton"
        )

        self.button_box.addButton(
            self.copy_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.button_box.addButton(
            self.details_button,
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.button_box.addButton(
            self.close_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        self.copy_button.clicked.connect(
            self._copy_result
        )

        self.details_button.clicked.connect(
            self._show_details
        )

        self.close_button.clicked.connect(
            self.reject
        )

        self.main_layout.addWidget(
            self.button_box
        )

    # ==========================================================
    # Data
    # ==========================================================

    def _load_analysis(
        self,
    ) -> None:

        model = str(
            self.analysis.get(
                "model"
            )
            or "Unknown model"
        ).strip()

        analysis_type = str(
            self.analysis.get(
                "type"
            )
            or "other"
        ).strip()

        created_at = str(
            self.analysis.get(
                "created_at"
            )
            or "Unknown time"
        ).strip()

        result = str(
            self.analysis.get(
                "result"
            )
            or ""
        ).strip()

        metadata = self.analysis.get(
            "metadata"
        )

        context_summary = self._extract_context_summary(
            metadata
        )

        self.model_label.setText(
            f"Model: {model}"
        )

        self.type_label.setText(
            f"Type: {analysis_type}"
        )

        self.created_label.setText(
            f"Created: {created_at}"
        )

        self.context_label.setText(
            context_summary
        )

        self.result_text.setPlainText(
            result
            or "The AI analysis did not contain any text."
        )

    # ==========================================================
    # Actions
    # ==========================================================

    def _copy_result(
        self,
    ) -> None:

        text = self.result_text.toPlainText()

        clipboard = (
            QGuiApplication.clipboard()
        )

        clipboard.setText(
            text
        )

        QMessageBox.information(
            self,
            "Copied",
            "The AI analysis was copied to the clipboard.",
        )

    def _show_details(
        self,
    ) -> None:

        details = {
            "id": self.analysis.get(
                "id"
            ),
            "case_id": self.analysis.get(
                "case_id"
            ),
            "type": self.analysis.get(
                "type"
            ),
            "model": self.analysis.get(
                "model"
            ),
            "confidence": self.analysis.get(
                "confidence"
            ),
            "created_at": self.analysis.get(
                "created_at"
            ),
            "metadata": self.analysis.get(
                "metadata"
            ),
        }

        QMessageBox.information(
            self,
            "AI analysis details",
            json.dumps(
                details,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _extract_context_summary(
        metadata: Any,
    ) -> str:

        if not isinstance(
            metadata,
            dict,
        ):

            return "Context: unavailable"

        context = metadata.get(
            "context"
        )

        if not isinstance(
            context,
            dict,
        ):

            return "Context: unavailable"

        message_count = (
            context.get(
                "related_messages"
            )
            or context.get(
                "messages"
            )
            or context.get(
                "selected_messages"
            )
            or 0
        )

        entity_count = (
            context.get(
                "related_entities"
            )
            or context.get(
                "entities"
            )
            or 0
        )

        evidence_count = (
            context.get(
                "related_evidence"
            )
            or context.get(
                "evidence"
            )
            or 0
        )

        timeline_count = (
            context.get(
                "related_timeline"
            )
            or context.get(
                "timeline"
            )
            or 0
        )

        return (
            "Context: "
            f"{message_count} messages, "
            f"{entity_count} entities, "
            f"{evidence_count} evidence, "
            f"{timeline_count} timeline events"
        )