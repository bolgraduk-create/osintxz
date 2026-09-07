"""
Application entry point.

Responsible for:

- initializing database session
- creating ServiceContainer
- starting desktop application

This is the only executable entry point.
"""

from __future__ import annotations

from app.database.session import SessionFactory

from app.core.service_container import ServiceContainer

from app.interface.desktop.desktop_app import (
    DesktopApplication,
)


def main() -> int:
    """
    Start application.
    """

    session = SessionFactory()

    try:

        container = ServiceContainer(
            session=session,
        )

        application = DesktopApplication(
            container=container,
        )

        return application.run()

    finally:

        session.close()


if __name__ == "__main__":
    raise SystemExit(main())