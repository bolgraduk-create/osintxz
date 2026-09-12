"""OSINTXZ application entry point.

The Qt Quick shell is the single authoritative desktop presentation. It uses
the existing application composition root and services.
"""

from __future__ import annotations

def main() -> int:
    """Start the backend-connected Qt Quick desktop UI."""
    from app.core.service_container import ServiceContainer
    from app.database.session import SessionFactory
    from app.interface.desktop.desktop_app import DesktopApplication

    session = SessionFactory()
    try:
        container = ServiceContainer(session=session)
        application = DesktopApplication(container=container)
        return application.run()
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
