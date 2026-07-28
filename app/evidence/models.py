"""
Evidence domain models.

Represents investigation evidence.
"""

from __future__ import annotations


from dataclasses import dataclass, field


from datetime import datetime, timezone


from uuid import UUID, uuid4


from typing import Any



@dataclass
class Evidence:
    """
    Investigation evidence entity.
    """

    case_id: UUID

    source: str

    content: Any


    metadata: dict[str, Any] = field(
        default_factory=dict
    )


    reliability: float = 0.5


    evidence_id: UUID = field(
        default_factory=uuid4
    )


    created_at: datetime = field(
        default_factory=lambda:
            datetime.now(
                timezone.utc
            )
    )



    def update_reliability(
        self,
        value: float,
    ) -> None:
        """
        Update evidence reliability.
        """

        if value < 0 or value > 1:

            raise ValueError(
                "Reliability must be between 0 and 1"
            )


        self.reliability = value



    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert evidence to dictionary.
        """

        return {

            "evidence_id":
                str(
                    self.evidence_id
                ),


            "case_id":
                str(
                    self.case_id
                ),


            "source":
                self.source,


            "content":
                self.content,


            "metadata":
                self.metadata,


            "reliability":
                self.reliability,


            "created_at":
                self.created_at.isoformat(),

        }