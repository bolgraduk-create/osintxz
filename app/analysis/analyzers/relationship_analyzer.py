"""
Relationship analyzer.

Analyzes communication patterns
and prepares relationship data
for graph and intelligence modules.

Architecture:

Messages
    ↓
RelationshipAnalyzer
    ↓
Relationship objects
    ↓
Graph / Services / Database
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from typing import Any


class RelationshipAnalyzer:
    """
    Advanced relationship analyzer.

    Responsible for detecting
    connections between entities.
    """


    # ==========================================================
    # Main analysis
    # ==========================================================

    def analyze(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Analyze messages and build
        relationship candidates.
        """


        relationships = (
            self.analyze_messages(
                messages
            )
        )


        for relationship in relationships:

            relationship["strength"] = (
                self.calculate_strength(
                    relationship
                )
            )

            relationship["confidence"] = (
                self.calculate_confidence(
                    relationship
                )
            )


        return relationships


    # ==========================================================
    # Message analysis
    # ==========================================================

    def analyze_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        stats = defaultdict(
            lambda: {
                "count": 0,
                "dates": [],
            }
        )


        for message in messages:

            sender = message.get(
                "sender"
            )

            receiver = message.get(
                "receiver"
            )


            if not sender or not receiver:
                continue


            key = (
                sender,
                receiver,
            )


            stats[key]["count"] += 1


            if message.get("date"):

                stats[key]["dates"].append(
                    message["date"]
                )


        result = []


        for (
            source,
            target,
        ), data in stats.items():

            result.append(
                {
                    "source": source,
                    "target": target,
                    "type": "communication",
                    "frequency": data["count"],
                    "dates": data["dates"],
                    "metadata": {},
                }
            )


        return result


    # ==========================================================
    # Participants
    # ==========================================================

    def extract_participants(
        self,
        messages: list[dict[str, Any]],
    ) -> list[str]:

        users = set()


        for message in messages:

            sender = message.get(
                "sender"
            )

            receiver = message.get(
                "receiver"
            )


            if sender:
                users.add(sender)


            if receiver:
                users.add(receiver)


        return list(users)


    # ==========================================================
    # Relationship metrics
    # ==========================================================

    def calculate_frequency(
        self,
        relationship: dict[str, Any],
    ) -> int:

        return relationship.get(
            "frequency",
            0,
        )


    def calculate_strength(
        self,
        relationship: dict[str, Any],
    ) -> float:
        """
        Calculate relationship strength.

        Current version uses frequency.
        Future versions will include:
        - sentiment
        - time
        - topics
        - mutual contacts
        """


        frequency = self.calculate_frequency(
            relationship
        )


        if frequency == 0:
            return 0.0


        strength = min(
            frequency / 100,
            1.0,
        )


        return round(
            strength,
            3,
        )


    def calculate_recency(
        self,
        dates: list[Any],
    ) -> float:

        if not dates:
            return 0.0


        return 1.0


    def calculate_confidence(
        self,
        relationship: dict[str, Any],
    ) -> float:

        frequency = (
            relationship.get(
                "frequency",
                0,
            )
        )


        if frequency >= 10:
            return 0.95


        if frequency >= 3:
            return 0.8


        return 0.6


    # ==========================================================
    # Graph preparation
    # ==========================================================

    def build_nodes(
        self,
        relationships: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        nodes = set()


        for relation in relationships:

            nodes.add(
                relation["source"]
            )

            nodes.add(
                relation["target"]
            )


        return [
            {
                "id": node
            }
            for node in nodes
        ]


    def build_edges(
        self,
        relationships: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        return relationships


    def export_graph(
        self,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:

        return {
            "nodes": self.build_nodes(
                relationships
            ),
            "edges": self.build_edges(
                relationships
            ),
        }


    # ==========================================================
    # Statistics
    # ==========================================================

    def relationship_statistics(
        self,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:

        return {
            "total_relationships": len(
                relationships
            ),
            "total_interactions": sum(
                r.get(
                    "frequency",
                    0,
                )
                for r in relationships
            ),
        }


    # ==========================================================
    # Export
    # ==========================================================

    def export(
        self,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:

        return {
            "relationships": relationships,
            "statistics": (
                self.relationship_statistics(
                    relationships
                )
            ),
            "graph": (
                self.export_graph(
                    relationships
                )
            ),
        }