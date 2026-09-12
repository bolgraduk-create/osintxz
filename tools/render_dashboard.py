"""Render the QML dashboard to a PNG for visual regression checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import PySide6

_pyside_dll_directory = None
if sys.platform == "win32":
    _pyside_dll_directory = os.add_dll_directory(
        str(Path(PySide6.__file__).resolve().parent)
    )

from PySide6.QtCore import Property, QObject, Signal, Slot, Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest


ROOT = Path(__file__).resolve().parents[1]
QML_FILE = ROOT / "app" / "interface" / "desktop" / "qml" / "Main.qml"
SCREENSHOT_DIR = ROOT / "design" / "screenshots"


class EmptyPreviewBridge(QObject):
    """Explicit development fixture used only by the screenshot renderer."""

    changed = Signal()
    navigationRequested = Signal(str)
    messageChanged = Signal()

    accountDisplayName = Property(str, lambda self: "Local workspace", constant=True)
    accountRole = Property(str, lambda self: "No authenticated user", constant=True)
    accountInitials = Property(str, lambda self: "LW", constant=True)
    databaseAvailable = Property(bool, lambda self: True, constant=True)
    currentCaseId = Property(str, lambda self: "", constant=True)
    currentCaseTitle = Property(str, lambda self: "", constant=True)
    hasCurrentCase = Property(bool, lambda self: False, constant=True)
    message = Property(str, lambda self: "", constant=True)
    dashboard = Property(
        "QVariantMap",
        lambda self: {
            "dateLabel": "EMPTY DEVELOPMENT STATE",
            "greeting": "Good afternoon.",
            "summary": "No active investigations. Create a case to begin analysis.",
            "activeCases": 0,
            "entities": 0,
            "findings": 0,
            "risks": 0,
            "recentCases": [],
            "recentIntelligence": [],
            "graphNodes": [],
            "graphEdges": [],
            "graphCaseTitle": "",
        },
        constant=True,
    )

    @Slot(str, str, result="QVariantMap")
    def pageData(self, page: str, query: str = "") -> dict:
        if page == "osint":
            records = []
        else:
            records = []
        return {
            "metrics": [
                {"title": "Items", "value": "0", "delta": "", "subtext": "No stored data", "color": "#68a4ff", "chart": "none"},
                {"title": "Available", "value": "0", "delta": "", "subtext": "No stored data", "color": "#36cfa1", "chart": "none"},
                {"title": "Pending", "value": "0", "delta": "", "subtext": "No stored data", "color": "#e5a84b", "chart": "none"},
            ],
            "records": records,
            "contextItems": [{"title": "No investigation selected", "detail": "Open a case to load its data", "color": "#8094a8"}],
            "emptyText": "No records available",
            "actionEnabled": page in {"cases", "osint"},
            "actionReason": "",
        }

    @Slot(str, result="QVariantList")
    def search(self, query: str) -> list:
        return []

    @Slot(str, result=bool)
    def selectCase(self, case_id: str) -> bool:
        return False

    @Slot(str, str, result=bool)
    def createCase(self, title: str, description: str = "") -> bool:
        return False

    @Slot(str, str)
    def activateRecord(self, page: str, record_id: str) -> None:
        return None

    @Slot(str, str, result=bool)
    def runOsint(self, target_type: str, value: str) -> bool:
        return False


def main() -> int:
    show_palette = "--palette" in sys.argv
    if show_palette:
        sys.argv.remove("--palette")

    use_real_data = "--real-data" in sys.argv
    if use_real_data:
        sys.argv.remove("--real-data")

    width, height = 1648, 928
    size_argument = next((arg for arg in sys.argv if arg.startswith("--size=")), None)
    if size_argument is not None:
        sys.argv.remove(size_argument)
        width, height = (int(value) for value in size_argument.removeprefix("--size=").split("x", 1))

    page = "overview"
    page_argument = next((arg for arg in sys.argv if arg.startswith("--page=")), None)
    if page_argument is not None:
        sys.argv.remove(page_argument)
        page = page_argument.removeprefix("--page=")

    if use_real_data and page == "overview":
        output_name = "dashboard_real.png"
    elif show_palette:
        output_name = "dashboard_palette.png"
    elif page != "overview":
        output_name = f"page_{page}.png"
    elif (width, height) == (1648, 928):
        output_name = "dashboard_current.png"
    else:
        output_name = f"dashboard_{width}x{height}.png"
    output_file = SCREENSHOT_DIR / output_name

    app = QGuiApplication(sys.argv)
    app.setFont(QFont("Segoe UI Variable", 10))

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_FILE.parent))
    session = None
    if use_real_data:
        from app.core.service_container import ServiceContainer
        from app.database.session import SessionFactory
        from app.interface.desktop.bridges import DesktopBridge

        session = SessionFactory()
        preview_bridge = DesktopBridge(ServiceContainer(session=session))
    else:
        preview_bridge = EmptyPreviewBridge()
    engine.rootContext().setContextProperty("desktopBridge", preview_bridge)
    engine.load(QUrl.fromLocalFile(str(QML_FILE)))
    if not engine.rootObjects():
        return 1

    window = engine.rootObjects()[0]
    window.setWidth(width)
    window.setHeight(height)
    window.setProperty("currentPage", page)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    def capture() -> None:
        screen = app.primaryScreen()
        pixmap = screen.grabWindow(window.winId(), 0, 0, window.width(), window.height())
        if pixmap.isNull() or not pixmap.save(str(output_file), "PNG"):
            app.exit(2)
            return
        print(output_file)
        app.quit()

    if show_palette:
        def open_palette() -> None:
            QTest.keyClick(
                window,
                Qt.Key.Key_K,
                Qt.KeyboardModifier.ControlModifier,
            )

        QTimer.singleShot(250, open_palette)

    QTimer.singleShot(900, capture)
    try:
        return app.exec()
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    raise SystemExit(main())
