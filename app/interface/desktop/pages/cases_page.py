"""
Cases page.

Responsible for:

- displaying investigation cases workspace
- creating investigations
- opening selected cases

Does NOT:

- execute business logic
- access database
- call services directly
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QWidget,
    QFrame,
)

from PySide6.QtCore import Qt


from app.interface.desktop.pages.base_page import (
    BasePage,
)



class CasesPage(BasePage):
    """
    Investigation cases workspace.
    """



    def __init__(
        self,
        container,
        open_case_callback=None,
    ):

        self.container = container

        self.open_case_callback = (
            open_case_callback
        )

        super().__init__(
            "Cases"
        )



    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create cases UI.
        """


        main_layout = QVBoxLayout(
            self
        )


        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        header_layout = QHBoxLayout()


        title = QLabel(
            "Investigation Cases"
        )

        title.setStyleSheet(
            """
            font-size: 24px;
            font-weight: bold;
            """
        )


        header_layout.addWidget(
            title
        )


        header_layout.addStretch()



        self.create_button = QPushButton(
            "+ Create Investigation"
        )


        self.create_button.clicked.connect(
            self._create_investigation
        )


        header_layout.addWidget(
            self.create_button
        )


        main_layout.addLayout(
            header_layout
        )



        # ------------------------------------------------------
        # Description
        # ------------------------------------------------------

        description = QLabel(
            "Manage investigation cases and open workspace."
        )


        description.setStyleSheet(
            """
            color: gray;
            font-size: 14px;
            """
        )


        main_layout.addWidget(
            description
        )



        # ------------------------------------------------------
        # Cases list
        # ------------------------------------------------------

        self.case_list = QListWidget()


        self.case_list.itemDoubleClicked.connect(
            self._open_case
        )


        main_layout.addWidget(
            self.case_list
        )



        self._load_cases()



    # ==========================================================
    # Loading
    # ==========================================================

    def _load_cases(
        self,
    ) -> None:

        self.case_list.clear()


        cases = (
            self.container
            .case_controller
            .get_cases()
        )


        for case in cases:


            widget = (
                self._create_case_card(
                    case
                )
            )


            item = QListWidgetItem()


            item.setSizeHint(
                widget.sizeHint()
            )


            item.setData(
                Qt.UserRole,
                case,
            )


            self.case_list.addItem(
                item
            )


            self.case_list.setItemWidget(
                item,
                widget,
            )



    # ==========================================================
    # Case card
    # ==========================================================

    def _create_case_card(
        self,
        case: dict,
    ) -> QWidget:
        """
        Create visual case card.
        """


        frame = QFrame()


        frame.setFrameShape(
            QFrame.StyledPanel
        )


        layout = QVBoxLayout(
            frame
        )


        title = QLabel(
            case.get(
                "title",
                "Untitled case",
            )
        )


        title.setStyleSheet(
            """
            font-size:18px;
            font-weight:bold;
            """
        )


        layout.addWidget(
            title
        )



        description = QLabel(
            case.get(
                "description",
                "No description",
            )
        )


        layout.addWidget(
            description
        )



        info = QLabel(
            f"ID: {case.get('id')}"
        )


        info.setStyleSheet(
            """
            color:gray;
            """
        )


        layout.addWidget(
            info
        )


        return frame



    # ==========================================================
    # Open case
    # ==========================================================

    def _open_case(
        self,
        item,
    ) -> None:


        case = (
            item.data(
                Qt.UserRole
            )
        )


        if case is None:
            return



        if self.open_case_callback:


            self.open_case_callback(
                case
            )



    # ==========================================================
    # Create
    # ==========================================================

    def _create_investigation(
        self,
    ) -> None:


        result = (
            self.container
            .case_controller
            .create_case()
        )


        print(
            result
        )


        self._load_cases()