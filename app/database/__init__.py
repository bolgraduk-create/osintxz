"""
Database package.

Provides database base classes.

Database sessions and engine
should be imported directly from
app.database.session when required.
"""

from app.database.base import (
    Base,
    BaseModel,
)


__all__ = [
    "Base",
    "BaseModel",
]