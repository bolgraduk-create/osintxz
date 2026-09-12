"""Opt-in, read-only integration check against the configured real database.

Run with OSINTXZ_VERIFY_REAL_UI=1. Never seeds, generates reports or runs connectors.
"""
import json
import os

import pytest


def test_failed_initial_query_can_retry_without_recursive_signal():
    from types import SimpleNamespace
    from app.interface.desktop.bridges import DesktopBridge

    class Service:
        def __init__(self):
            self.offsets = []

        def count_all(self, **kwargs):
            return 101

        def get_page(self, *, limit, offset, case_id):
            self.offsets.append(offset)
            if len(self.offsets) == 1:
                raise RuntimeError("Temporary query failure")
            return [{"id": str(i), "value": str(i)} for i in range(offset, min(offset + limit, 101))]

    service = Service()
    container = SimpleNamespace(case_controller=SimpleNamespace(get_cases=lambda: []), entity_service=service)
    bridge = DesktopBridge(container)
    notifications = []
    bridge.changed.connect(lambda: notifications.append(True))
    failed = bridge.pageData("entities", "")
    assert "Unable" in failed["emptyText"]
    assert not failed["loading"]
    assert "entities" not in bridge._page_records
    assert not notifications
    first = bridge.pageData("entities", "")
    assert len(first["records"]) == 100
    assert first["hasMore"]
    bridge.loadMore("entities")
    last = bridge.pageData("entities", "missing")
    assert not last["hasMore"], "Filtering must not change the pagination cursor"
    assert service.offsets == [0, 0, 100]
    assert len(bridge._page_records["entities"]) == 101


@pytest.mark.skipif(os.environ.get("OSINTXZ_VERIFY_REAL_UI") != "1", reason="Requires local database")
def test_real_initial_loading_and_scroll():
    from tools.render_dashboard import QML_FILE, SCREENSHOT_DIR
    from PySide6.QtCore import QObject, QUrl, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtGui import QFont
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    from sqlalchemy import func, select, text
    from app.core.service_container import ServiceContainer
    from app.database.session import SessionFactory
    from app.interface.desktop.bridges import DesktopBridge
    from app.models.entity import Entity
    from app.models.evidence import Evidence
    from app.models.report import Report
    from app.models.timeline_event import TimelineEvent

    app = QGuiApplication.instance() or QGuiApplication([])
    app.setFont(QFont("Segoe UI Variable", 10))
    warnings = []
    previous = qInstallMessageHandler(lambda kind, ctx, message: warnings.append(message))
    session = SessionFactory()
    session.bind.echo = False
    session.execute(text("SET TRANSACTION READ ONLY"))
    engine = QQmlApplicationEngine()
    try:
        bridge = DesktopBridge(ServiceContainer(session=session))
        engine.rootContext().setContextProperty("desktopBridge", bridge)
        engine.load(QUrl.fromLocalFile(str(QML_FILE)))
        assert engine.rootObjects(), warnings
        window = engine.rootObjects()[0]
        result = {}
        counts = {}
        for page, cls in (("timeline", TimelineEvent), ("entities", Entity), ("evidence", Evidence), ("reports", Report)):
            statement = select(func.count(cls.id))
            if hasattr(cls, "deleted_at"):
                statement = statement.where(cls.deleted_at.is_(None))
            total = session.scalar(statement)
            window.setProperty("currentPage", page)
            QTest.qWait(250)
            view = window.findChild(QObject, "recordsView")
            assert view is not None, (page, warnings)
            count = view.property("count")
            assert count == min(100, total), (page, count, total, warnings)
            assert bridge.pageData(page, "")["total"] == total
            assert not bridge.pageData(page, "")["loading"]
            assert view.property("height") > 0
            if total:
                assert view.property("contentHeight") >= count * 64
                # Move the actual QML view, exercising its near-bottom handler.
                view.setProperty("contentY", view.property("contentHeight") - view.property("height"))
                QTest.qWait(100)
                assert view.property("count") == min(200, total), (page, view.property("count"))
                if total > 100:
                    assert view.property("contentY") > 0, "Appending must preserve scroll position"
            else:
                assert "Unable" not in bridge.pageData(page, "")["emptyText"]
            counts[page] = view.property("count")
            result[page] = {"total": total, "first_page": count, "after_scroll": counts[page]}
            window.grabWindow().save(str(SCREENSHOT_DIR / ("verified_" + page + ".png")))
        for _ in range(3):
            for page in ("overview", "timeline", "evidence", "osint", "reports", "settings", "entities"):
                window.setProperty("currentPage", page)
                QTest.qWait(30)
                if page in counts:
                    view = window.findChild(QObject, "recordsView")
                    assert view is not None
                    assert view.property("count") == counts[page]
        assert not warnings, warnings
        from uuid import UUID, uuid4
        for case in bridge._cases:
            case_id = UUID(case["id"])
            assert bridge.selectCase(str(case_id))
            for page, cls in (("timeline", TimelineEvent), ("entities", Entity), ("evidence", Evidence), ("reports", Report)):
                statement = select(func.count(cls.id)).where(cls.case_id == case_id)
                if hasattr(cls, "deleted_at"):
                    statement = statement.where(cls.deleted_at.is_(None))
                total = session.scalar(statement)
                data = bridge.pageData(page, "")
                assert data["total"] == total
                assert len(data["records"]) == min(100, total)
        # An absent scope really returns zero; all-data scope was checked above.
        assert bridge._container.report_service.count_all(case_id=uuid4()) == 0
        print("REAL UI VALIDATION " + json.dumps(result))
    finally:
        import shiboken6
        shiboken6.delete(engine)
        session.rollback()
        session.close()
        qInstallMessageHandler(previous)
