"""
Collection data models.

Defines normalized objects
returned by collectors.
"""

from __future__ import annotations


from dataclasses import dataclass, field


from datetime import datetime, timezone


from typing import Any



@dataclass
class CollectedData:
    """
    Standard collector result.
    """

    source: str

    content: Any

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    collected_at: datetime = field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )



    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert data to dictionary.
        """

        return {

            "source":
                self.source,


            "content":
                self.content,


            "metadata":
                self.metadata,


            "collected_at":
                self.collected_at.isoformat(),

        }