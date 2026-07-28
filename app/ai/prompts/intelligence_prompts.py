"""
Intelligence prompts.

Contains AI prompt templates
for investigation workflows.
"""

from __future__ import annotations


class IntelligencePrompts:
    """
    Static collection of intelligence prompts.
    """


    @staticmethod
    def investigation_analysis(
        context: str,
    ) -> str:
        """
        General investigation analysis.
        """

        return f"""
You are an intelligence analyst.

Analyze investigation data.

Tasks:

- identify important facts
- identify entities
- find relationships
- detect patterns
- create conclusions

Investigation data:

{context}

Provide structured intelligence analysis.
"""


    @staticmethod
    def entity_analysis(
        context: str,
    ) -> str:
        """
        Entity extraction.
        """

        return f"""
Extract entities from investigation data.

Find:

- persons
- organizations
- locations
- objects

Data:

{context}
"""


    @staticmethod
    def relationship_analysis(
        context: str,
    ) -> str:
        """
        Relationship analysis.
        """

        return f"""
Analyze connections between entities.

Find:

- direct links
- communication
- cooperation
- hidden relations

Data:

{context}
"""


    @staticmethod
    def summary(
        context: str,
    ) -> str:
        """
        Investigation summary.
        """

        return f"""
Create investigation summary.

Include:

- main facts
- important entities
- relationships
- conclusions

Data:

{context}
"""