"""
Tests for centrality analyzer.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
    GraphEdge,
)


from app.analysis.centrality_analyzer import (
    CentralityAnalyzer,
)



def test_degree_centrality():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()
    third = uuid4()


    graph.add_node(
        GraphNode(
            entity_id=first,
            label="A",
            entity_type="person",
        )
    )


    graph.add_node(
        GraphNode(
            entity_id=second,
            label="B",
            entity_type="person",
        )
    )


    graph.add_node(
        GraphNode(
            entity_id=third,
            label="C",
            entity_type="person",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=third,
            relationship_type="knows",
        )
    )


    analyzer = CentralityAnalyzer(
        graph
    )


    result = analyzer.degree_centrality()


    assert result[first] == 2
    assert result[second] == 1
    assert result[third] == 1



def test_most_connected():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    graph.add_node(
        GraphNode(
            entity_id=first,
            label="Main",
            entity_type="person",
        )
    )


    graph.add_node(
        GraphNode(
            entity_id=second,
            label="Other",
            entity_type="person",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=first,
            target_id=second,
            relationship_type="knows",
        )
    )


    analyzer = CentralityAnalyzer(
        graph
    )


    result = analyzer.get_most_connected()


    assert result[0][0] == first