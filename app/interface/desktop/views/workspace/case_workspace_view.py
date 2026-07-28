"""
Case workspace view.

Responsible for:

- workspace tabs UI
- displaying case sections

Does NOT:

- access database
- execute business logic
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QLabel,
)


from app.interface.desktop.views.evidence_workspace_view import (
    EvidenceWorkspaceView,
)


from app.interface.desktop.views.entity_workspace_view import (
    EntityWorkspaceView,
)


from app.interface.desktop.views.relationship_workspace_view import (
    RelationshipWorkspaceView,
)


from app.interface.desktop.views.timeline_workspace_view import (
    TimelineWorkspaceView,
)


from app.interface.desktop.views.report_workspace_view import (
    ReportWorkspaceView,
)



class CaseWorkspaceView(QWidget):
    """
    Main case workspace UI container.
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
        Create workspace tabs.
        """


        layout = QVBoxLayout(
            self
        )


        self.tabs = QTabWidget()



        # ======================================================
        # Overview
        # ======================================================

        self.overview_view = QLabel(
            "Case Overview"
        )


        self.tabs.addTab(
            self.overview_view,
            "Overview",
        )



        # ======================================================
        # Evidence
        # ======================================================

        self.evidence_view = (
            EvidenceWorkspaceView()
        )


        self.tabs.addTab(
            self.evidence_view,
            "Evidence",
        )



        # ======================================================
        # Entities
        # ======================================================

        self.entity_view = (
            EntityWorkspaceView()
        )


        self.tabs.addTab(
            self.entity_view,
            "Entities",
        )



        # ======================================================
        # Relationships
        # ======================================================

        self.relationship_view = (
            RelationshipWorkspaceView()
        )


        self.tabs.addTab(
            self.relationship_view,
            "Relationships",
        )



        # ======================================================
        # Timeline
        # ======================================================

        self.timeline_view = (
            TimelineWorkspaceView()
        )


        self.tabs.addTab(
            self.timeline_view,
            "Timeline",
        )



        # ======================================================
        # Reports
        # ======================================================

        self.report_view = (
            ReportWorkspaceView()
        )


        self.tabs.addTab(
            self.report_view,
            "Reports",
        )



        # ======================================================
        # AI
        # ======================================================

        ai = QLabel(
            "AI Assistant Workspace"
        )


        self.tabs.addTab(
            ai,
            "AI Assistant",
        )



        layout.addWidget(
            self.tabs
        )