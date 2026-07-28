"""
Tests for EntityGraph model.
"""

from uuid import uuid4


from app.models.entity_graph import (
    EntityGraph,
    GraphNode,
    GraphEdge,
)



def test_add_node():

    graph = EntityGraph()


    node_id = uuid4()


    node = GraphNode(
        entity_id=node_id,
        label="John",
        entity_type="person",
    )


    graph.add_node(
        node
    )


    assert (
        node_id
        in graph.nodes
    )



def test_add_edge():

    graph = EntityGraph()


    first = uuid4()
    second = uuid4()


    edge = GraphEdge(
        source_id=first,
        target_id=second,
        relationship_type="knows",
    )


    graph.add_edge(
        edge
    )


    assert len(
        graph.edges
    ) == 1



def test_neighbors():

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


    neighbors = graph.get_neighbors(
        first
    )


    assert second in neighbors