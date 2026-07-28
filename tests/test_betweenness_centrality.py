"""
Tests for betweenness centrality.
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



def test_bridge_node_has_high_score():

    graph = EntityGraph()


    a = uuid4()
    b = uuid4()
    bridge = uuid4()
    c = uuid4()
    d = uuid4()


    for node in [
        a,
        b,
        bridge,
        c,
        d,
    ]:
        graph.add_node(
            GraphNode(
                entity_id=node,
                label=str(node),
                entity_type="person",
            )
        )


    graph.add_edge(
        GraphEdge(
            source_id=a,
            target_id=b,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=b,
            target_id=bridge,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=bridge,
            target_id=c,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=c,
            target_id=d,
            relationship_type="knows",
        )
    )


    analyzer = CentralityAnalyzer(
        graph
    )


    scores = analyzer.betweenness_centrality()


    assert scores[bridge] > 0