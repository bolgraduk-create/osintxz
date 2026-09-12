"""
Authoritative desktop application.

Responsible for:

- creating QApplication
- creating the Qt Quick engine
- exposing the existing application container through a QML bridge
- starting desktop UI

Does NOT:

- execute business logic
- access repositories
- perform investigation processing
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import PySide6

_pyside_dll_directory = None
if sys.platform == "win32":
    _pyside_dll_directory = os.add_dll_directory(
        str(Path(PySide6.__file__).resolve().parent)
    )

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from app.interface.desktop.bridges import DesktopBridge


class DesktopApplication:
    """
    Desktop application bootstrap.
    """

    def __init__(
        self,
        container,
    ) -> None:

        self.container = container
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

        self.app = QApplication(
            sys.argv,
        )

        self.app.setApplicationName("OSINTXZ")

        self.app.setOrganizationName("OSINTXZ")

        self.app.setFont(QFont("Segoe UI Variable", 10))

        base_dir = Path(__file__).resolve().parent
        qml_file = base_dir / "qml" / "Main.qml"

        self.bridge = DesktopBridge(container=self.container)
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(str(base_dir / "qml"))
        self.engine.rootContext().setContextProperty(
            "desktopBridge",
            self.bridge,
        )
        self.engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self.engine.rootObjects():
            raise RuntimeError(
                f"Unable to load the desktop interface: {qml_file}"
            )

        self.window = self.engine.rootObjects()[0]

    # ==========================================================
    # Run
    # ==========================================================

    def run(
        self,
    ) -> int:
        """
        Start desktop application.
        """

        return self.app.exec()
