"""
OSINT Intelligence Platform.

Desktop application entry point.
"""

from __future__ import annotations

from app.core.application import (
    Application,
)


def main() -> int:
    """
    Start desktop application.
    """

    app = Application()

    return app.run()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )