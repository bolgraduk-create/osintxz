"""
Tests for cluster scoring.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
    GraphEdge,
)


from app.analysis.cluster_analyzer import (
    ClusterAnalyzer,
)



def test_cluster_score():

    graph = EntityGraph()


    a = uuid4()
    b = uuid4()
    c = uuid4()


    for node in [
        a,
        b,
        c,
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
            target_id=c,
            relationship_type="knows",
        )
    )


    analyzer = ClusterAnalyzer(
        graph
    )


    result = analyzer.score_clusters()


    cluster, score = result[0]


    assert len(cluster) == 3

    assert score > 3