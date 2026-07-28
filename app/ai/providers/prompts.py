"""
AI Prompts.

Contains prompt templates
for intelligence analysis.
"""

from __future__ import annotations

from typing import Any



class IntelligencePrompts:
    """
    Prompt builder for OSINT analysis.
    """


    @staticmethod
    def investigation_analysis(
        context: dict[str, Any],
    ) -> str:
        """
        General investigation analysis prompt.
        """


        return f"""
You are an OSINT intelligence analyst.

Your task is to analyze an investigation
and create a structured intelligence assessment.


Investigation:

CASE:
{context.get("case")}


EVIDENCE:
{context.get("evidence")}


ENTITIES:
{context.get("entities")}


RELATIONSHIPS:
{context.get("relationships")}


Provide:

1. Key findings
2. Important entities
3. Relationship analysis
4. Possible connections
5. Missing information
6. Further investigation recommendations


Do not invent facts.
Separate confirmed information
from assumptions.
"""



    @staticmethod
    def relationship_analysis(
        entities: list[Any],
        relationships: list[Any],
    ) -> str:
        """
        Relationship graph analysis prompt.
        """


        return f"""
You are analyzing an OSINT relationship network.


ENTITIES:

{entities}


RELATIONSHIPS:

{relationships}


Analyze:

- strongest connections
- central entities
- suspicious patterns
- possible hidden relationships


Only use provided information.
"""



    @staticmethod
    def conclusion(
        analysis: str,
    ) -> str:
        """
        Generate final investigation conclusion.
        """


        return f"""
You are preparing a final intelligence conclusion.


Analysis:

{analysis}


Create:

1. Summary
2. Main conclusions
3. Confidence level
4. Limitations
5. Recommended next steps


Avoid unsupported claims.
"""