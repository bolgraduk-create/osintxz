"""
Evidence workspace view.

Responsible for:

- displaying evidence objects
- showing evidence details

Does NOT:

- access database
- execute business logic
- process files
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QTextEdit,
)



class EvidenceWorkspaceView(QWidget):
    """
    Evidence tab workspace.
    """



    def __init__(
        self,
    ):

        super().__init__()


        self.evidence = []


        self._setup_ui()



    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create evidence interface.
        """


        layout = QVBoxLayout(
            self
        )


        self.title = QLabel(
            "Evidence Objects"
        )


        layout.addWidget(
            self.title
        )



        self.list = QListWidget()


        self.list.itemClicked.connect(
            self._show_details
        )


        layout.addWidget(
            self.list
        )



        self.details = QTextEdit()


        self.details.setReadOnly(
            True
        )


        layout.addWidget(
            self.details
        )



    # ==========================================================
    # Data
    # ==========================================================

    def set_evidence(
        self,
        evidence: list,
    ) -> None:
        """
        Display evidence list.
        """


        self.evidence = evidence


        self.list.clear()


        for item in evidence:

            title = (
                item.get(
                    "title",
                    "Evidence"
                )
            )


            evidence_type = (
                item.get(
                    "type",
                    "unknown"
                )
            )


            self.list.addItem(

                f"{title} [{evidence_type}]"

            )



    # ==========================================================
    # Details
    # ==========================================================

    def _show_details(
        self,
        item,
    ) -> None:
        """
        Display selected evidence details.
        """


        index = (
            self.list.row(
                item
            )
        )


        if index >= len(
            self.evidence
        ):
            return



        evidence = (
            self.evidence[index]
        )



        self.details.setText(

            f"""
Title:

{evidence.get('title')}


Type:

{evidence.get('type')}


Value:

{evidence.get('value')}


ID:

{evidence.get('id')}
"""

        )