"""
Legacy application import compatibility.

The authoritative desktop bootstrap is:

    main.py
        -> app.interface.desktop.desktop_app.DesktopApplication

This module intentionally contains no QApplication, database-session,
ServiceContainer, theme, or MainWindow construction.

It remains only so older imports of ``app.core.application.Application``
do not create a second application bootstrap implementation.
"""

from __future__ import annotations

from app.interface.desktop.desktop_app import (
    DesktopApplication,
)


Application = DesktopApplication


__all__ = [
    "Application",
    "DesktopApplication",
]
