"""
Tests for connection strength.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphEdge,
)


from app.analysis.connection_analyzer import (
    ConnectionAnalyzer,
)



def test_connection_strength():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
            confidence=0.4,
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="called",
            confidence=0.9,
        )
    )


    analyzer = ConnectionAnalyzer(
        graph
    )


    strength = analyzer.get_connection_strength(
        first,
        second,
    )


    assert strength == 0.9



def test_no_connection_strength():

    graph = EntityGraph()


    analyzer = ConnectionAnalyzer(
        graph
    )


    result = analyzer.get_connection_strength(
        uuid4(),
        uuid4(),
    )


    assert result == 0.0