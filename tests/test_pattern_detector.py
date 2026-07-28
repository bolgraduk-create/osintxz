"""
Tests for pattern detector.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
    GraphEdge,
)


from app.analysis.pattern_detector import (
    PatternDetector,
)



def test_high_degree_node():

    graph = EntityGraph()


    center = uuid4()

    nodes = [
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    ]


    graph.add_node(
        GraphNode(
            entity_id=center,
            label="center",
            entity_type="account",
        )
    )


    for node in nodes:

        graph.add_node(
            GraphNode(
                entity_id=node,
                label=str(node),
                entity_type="person",
            )
        )


        graph.add_edge(
            GraphEdge(
                source_id=center,
                target_id=node,
                relationship_type="connected",
            )
        )


    detector = PatternDetector(
        graph
    )


    result = detector.find_high_degree_nodes(
        threshold=3
    )


    assert center in result