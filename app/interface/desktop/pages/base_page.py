"""
Base desktop page.

Responsible for:

- common page structure
- shared UI foundation

Does NOT:

- execute business logic
- access database
- perform analysis
"""

from __future__ import annotations


from PySide6.QtWidgets import (
    QWidget,
)



class BasePage(QWidget):
    """
    Base class for application pages.
    """



    def __init__(
        self,
        title: str,
    ):

        super().__init__()


        self.title = title


        self._setup_ui()



    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Setup page UI.

        Child pages override this.
        """

        pass



    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, str]:
        """
        Page metadata.
        """


        return {

            "type":
                "desktop_page",

            "title":
                self.title,

        }