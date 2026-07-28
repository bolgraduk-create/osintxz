"""
Full entity graph intelligence flow test.
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


from app.analysis.cluster_analyzer import (
    ClusterAnalyzer,
)


from app.analysis.pattern_detector import (
    PatternDetector,
)



def test_full_graph_analysis_flow():

    graph = EntityGraph()


    center = uuid4()

    a = uuid4()
    b = uuid4()
    c = uuid4()


    for node in [
        center,
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


    for node in [
        a,
        b,
        c,
    ]:
        graph.add_edge(
            GraphEdge(
                source_id=center,
                target_id=node,
                relationship_type="knows",
            )
        )


    # centrality

    centrality = CentralityAnalyzer(
        graph
    )


    ranking = centrality.rank_entities()


    assert ranking[0][0] == center



    # clusters

    clusters = ClusterAnalyzer(
        graph
    ).find_clusters()


    assert len(clusters) == 1



    # suspicious patterns

    suspicious = PatternDetector(
        graph
    ).find_high_degree_nodes(
        threshold=3
    )


    assert center in suspicious