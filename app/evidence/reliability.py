"""
Source reliability rules.

Provides reliability estimation
based on source type.
"""

from __future__ import annotations


from enum import Enum



class SourceReliabilityLevel(
    str,
    Enum,
):
    """
    Reliability categories.
    """

    HIGH = "high"

    MEDIUM = "medium"

    LOW = "low"



class SourceReliability:
    """
    Calculates source reliability.
    """



    DEFAULT_SCORE = 0.3



    SCORES = {

        "official_document":
            0.95,


        "government":
            0.95,


        "verified_account":
            0.85,


        "telegram":
            0.60,


        "social_media":
            0.50,


        "unknown":
            0.30,

    }



    def get_score(
        self,
        source_type: str,
    ) -> float:
        """
        Return reliability score.
        """

        return self.SCORES.get(
            source_type,
            self.DEFAULT_SCORE,
        )



    def get_level(
        self,
        score: float,
    ) -> SourceReliabilityLevel:
        """
        Convert score to level.
        """

        if score >= 0.8:

            return (
                SourceReliabilityLevel.HIGH
            )


        if score >= 0.5:

            return (
                SourceReliabilityLevel.MEDIUM
            )


        return (
            SourceReliabilityLevel.LOW
        )