"""
Case workspace page.

Responsible for:

- displaying selected investigation workspace
- connecting workspace data with views

Does NOT:

- execute business logic
- access database directly
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)

from app.interface.desktop.views.workspace.case_workspace_view import (
    CaseWorkspaceView,
)


class CaseWorkspacePage(BasePage):
    """
    Workspace for selected case.
    """

    def __init__(
        self,
        container,
    ):

        self.container = container

        self.case = None

        super().__init__(
            "Case Workspace"
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create workspace UI.
        """

        layout = QVBoxLayout(
            self
        )

        self.workspace_view = (
            CaseWorkspaceView()
        )

        layout.addWidget(
            self.workspace_view
        )

    # ==========================================================
    # Loading
    # ==========================================================

    def load_case(
        self,
        case: dict,
    ) -> None:
        """
        Load selected case workspace.
        """

        self.case = case

        workspace = (
            self.container
            .workspace_controller
            .load_workspace(
                case["id"]
            )
        )

        if workspace is None:
            return

        case_data = workspace["case"]

        statistics = workspace["statistics"]

        overview_text = f"""
Case:

{case_data['title']}


Description:

{case_data['description']}


Statistics:

Evidence: {statistics['evidence']}

Entities: {statistics['entities']}

Relationships: {statistics['relationships']}

Reports: {statistics['reports']}

Timeline: {statistics['timeline']}
"""

        self.workspace_view.overview_view.setText(
            overview_text
        )

        self.workspace_view.evidence_view.set_evidence(
            workspace.get(
                "evidence",
                [],
            )
        )

        self.workspace_view.entity_view.set_entities(
            workspace.get(
                "entities",
                [],
            )
        )

        self.workspace_view.relationship_view.set_relationships(
            workspace.get(
                "relationships",
                [],
            )
        )

        self.workspace_view.timeline_view.set_events(
            workspace.get(
                "timeline",
                [],
            )
        )

        self.workspace_view.report_view.set_reports(
            workspace.get(
                "reports",
                [],
            )
        )