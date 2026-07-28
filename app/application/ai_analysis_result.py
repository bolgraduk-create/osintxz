"""
AI analysis result.

Represents a normalized result returned
by AI application services.

Responsible for:

- storing AI response
- reporting execution status
- carrying optional metadata

Does NOT:

- execute AI
- access database
- contain UI logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AIAnalysisResult:
    """
    Normalized AI result.
    """

    success: bool

    message: str

    content: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )