"""
Tests for ConnectionAnalyzer.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphEdge,
)


from app.analysis.connection_analyzer import (
    ConnectionAnalyzer,
)



def test_get_connections():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    analyzer = ConnectionAnalyzer(
        graph
    )


    result = analyzer.get_connections(
        first
    )


    assert second in result



def test_has_connection():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    analyzer = ConnectionAnalyzer(
        graph
    )


    assert analyzer.has_connection(
        first,
        second,
    )



def test_count_connections():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    analyzer = ConnectionAnalyzer(
        graph
    )


    assert analyzer.count_connections(
        first
    ) == 1