"""
Tests for connection path finding.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphEdge,
)


from app.analysis.connection_analyzer import (
    ConnectionAnalyzer,
)



def test_find_path():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()
    third = uuid4()


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=second,
            target_id=third,
            relationship_type="knows",
        )
    )


    analyzer = ConnectionAnalyzer(
        graph
    )


    path = analyzer.find_path(
        first,
        third,
    )


    assert path == [
        first,
        second,
        third,
    ]