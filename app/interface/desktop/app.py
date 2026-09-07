"""
Legacy desktop application import compatibility.

The canonical implementation lives in:

    app.interface.desktop.desktop_app.DesktopApplication

This module must not create QApplication, containers, sessions, themes,
or windows independently. It exists only for compatibility with older
imports.
"""

from __future__ import annotations

from app.interface.desktop.desktop_app import (
    DesktopApplication,
)


__all__ = [
    "DesktopApplication",
]
