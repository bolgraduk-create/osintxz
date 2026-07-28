"""
Tests for cluster analyzer.
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



def test_find_clusters():

    graph = EntityGraph()


    a = uuid4()
    b = uuid4()
    c = uuid4()
    isolated = uuid4()


    for node in [
        a,
        b,
        c,
        isolated,
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


    clusters = analyzer.find_clusters()


    assert len(clusters) == 2


    assert any(
        len(cluster) == 3
        for cluster in clusters
    )