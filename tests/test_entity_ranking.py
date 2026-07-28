"""
Tests for entity ranking.
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



def test_entity_ranking():

    graph = EntityGraph()


    main = uuid4()
    second = uuid4()
    third = uuid4()


    for node in [
        main,
        second,
        third,
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
            source_id=main,
            target_id=second,
            relationship_type="knows",
        )
    )


    graph.add_edge(
        GraphEdge(
            source_id=main,
            target_id=third,
            relationship_type="knows",
        )
    )


    analyzer = CentralityAnalyzer(
        graph
    )


    ranking = analyzer.rank_entities()


    assert ranking[0][0] == main