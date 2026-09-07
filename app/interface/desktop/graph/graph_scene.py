"""
Graph graphics scene.

Responsible for:

- creating graph node items
- creating graph edge items
- storing displayed graph items
- applying the initial circular layout
- calculating the graph scene bounds
- clearing previously displayed graph data

Does NOT:

- access the database
- call application services
- execute graph analysis
- manage zooming or viewport navigation
"""

from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import (
    QRectF,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsScene,
)

from app.interface.desktop.graph.graph_edge_item import (
    GraphEdgeItem,
)
from app.interface.desktop.graph.graph_node_item import (
    GraphNodeItem,
)


class GraphScene(QGraphicsScene):
    """
    Graphics scene containing entity graph nodes and edges.
    """

    node_selected = Signal(
        object,
    )

    edge_selected = Signal(
        object,
    )

    selection_cleared = Signal()

    DEFAULT_SCENE_WIDTH = 1600.0
    DEFAULT_SCENE_HEIGHT = 1000.0

    MINIMUM_LAYOUT_RADIUS = 260.0
    NODE_SPACING = 110.0

    SCENE_PADDING = 180.0

    def __init__(
        self,
        parent=None,
    ) -> None:

        super().__init__(
            parent,
        )

        self._node_items: dict[
            str,
            GraphNodeItem,
        ] = {}

        self._edge_items: list[
            GraphEdgeItem
        ] = []

        self._graph_data: dict[
            str,
            Any,
        ] = {
            "nodes": [],
            "edges": [],
            "statistics": {},
        }

        self._setup_scene()

    # ==========================================================
    # Setup
    # ==========================================================

    def _setup_scene(
        self,
    ) -> None:
        """
        Configure the base graphics scene.
        """

        self.setSceneRect(
            QRectF(
                -self.DEFAULT_SCENE_WIDTH / 2.0,
                -self.DEFAULT_SCENE_HEIGHT / 2.0,
                self.DEFAULT_SCENE_WIDTH,
                self.DEFAULT_SCENE_HEIGHT,
            )
        )

        self.setBackgroundBrush(
            QColor(
                "#151b24"
            )
        )

        self.selectionChanged.connect(
            self._handle_selection_changed
        )

    # ==========================================================
    # Graph loading
    # ==========================================================

    def set_graph_data(
        self,
        graph_data: dict[str, Any] | None,
    ) -> None:
        """
        Replace the currently displayed graph.

        Expected structure:

        {
            "nodes": [
                {
                    "id": "...",
                    "label": "...",
                    "type": "...",
                    "degree": 0,
                }
            ],
            "edges": [
                {
                    "id": "...",
                    "source": "...",
                    "target": "...",
                    "type": "...",
                    "confidence": 1.0,
                }
            ],
            "statistics": {}
        }
        """

        self.clear_graph()

        if not graph_data:
            self._graph_data = {
                "nodes": [],
                "edges": [],
                "statistics": {},
            }

            self._reset_scene_rect()

            return

        self._graph_data = {
            "nodes": list(
                graph_data.get(
                    "nodes",
                    [],
                )
            ),
            "edges": list(
                graph_data.get(
                    "edges",
                    [],
                )
            ),
            "statistics": dict(
                graph_data.get(
                    "statistics",
                    {},
                )
            ),
        }

        self._create_nodes(
            self._graph_data["nodes"]
        )

        self._create_edges(
            self._graph_data["edges"]
        )

        self.apply_circular_layout()

        self._update_scene_rect()

    def clear_graph(
        self,
    ) -> None:
        """
        Remove all graph items from the scene.
        """

        for edge_item in tuple(
            self._edge_items
        ):
            edge_item.detach()

        self.clear()

        self._node_items.clear()
        self._edge_items.clear()

        self._graph_data = {
            "nodes": [],
            "edges": [],
            "statistics": {},
        }

    # ==========================================================
    # Item creation
    # ==========================================================

    def _create_nodes(
        self,
        nodes: list[dict[str, Any]],
    ) -> None:
        """
        Create graphical node items.
        """

        for node_data in nodes:

            entity_id = str(
                node_data.get(
                    "id",
                    "",
                )
            ).strip()

            if not entity_id:
                continue

            if entity_id in self._node_items:
                continue

            label = str(
                node_data.get(
                    "label",
                    "Unknown entity",
                )
            )

            entity_type = str(
                node_data.get(
                    "type",
                    "unknown",
                )
            )

            degree_value = node_data.get(
                "degree",
                0,
            )

            try:
                degree = int(
                    degree_value
                )

            except (
                TypeError,
                ValueError,
            ):
                degree = 0

            node_item = GraphNodeItem(
                entity_id=entity_id,
                label=label,
                entity_type=entity_type,
                degree=degree,
            )

            node_item.setData(
                0,
                dict(
                    node_data
                ),
            )

            self.addItem(
                node_item
            )

            self._node_items[
                entity_id
            ] = node_item

    def _create_edges(
        self,
        edges: list[dict[str, Any]],
    ) -> None:
        """
        Create graphical relationship edge items.
        """

        for edge_data in edges:

            source_id = str(
                edge_data.get(
                    "source",
                    "",
                )
            ).strip()

            target_id = str(
                edge_data.get(
                    "target",
                    "",
                )
            ).strip()

            source_item = self._node_items.get(
                source_id
            )

            target_item = self._node_items.get(
                target_id
            )

            if (
                source_item is None
                or target_item is None
            ):
                continue

            relationship_type = str(
                edge_data.get(
                    "type",
                    "related_to",
                )
            )

            confidence_value = edge_data.get(
                "confidence",
                1.0,
            )

            try:
                confidence = float(
                    confidence_value
                )

            except (
                TypeError,
                ValueError,
            ):
                confidence = 1.0

            edge_item = GraphEdgeItem(
                source=source_item,
                target=target_item,
                relationship_type=relationship_type,
                confidence=confidence,
            )

            edge_item.setData(
                0,
                dict(
                    edge_data
                ),
            )

            self.addItem(
                edge_item
            )

            self._edge_items.append(
                edge_item
            )

    # ==========================================================
    # Layout
    # ==========================================================

    def apply_circular_layout(
        self,
    ) -> None:
        """
        Position all nodes around a circle.

        Nodes with more connections are placed first so that
        their initial positions are stable and predictable.
        """

        node_items = list(
            self._node_items.values()
        )

        node_count = len(
            node_items
        )

        if node_count == 0:
            self._reset_scene_rect()
            return

        node_items.sort(
            key=lambda item: (
                -item.degree,
                item.label.lower(),
                item.entity_id,
            )
        )

        if node_count == 1:

            node_item = node_items[0]

            node_item.setPos(
                -node_item.NODE_WIDTH / 2.0,
                -node_item.NODE_HEIGHT / 2.0,
            )

            node_item.update_edges()

            self._update_scene_rect()

            return

        circumference_radius = (
            node_count
            * self.NODE_SPACING
            / (
                2.0
                * math.pi
            )
        )

        radius = max(
            self.MINIMUM_LAYOUT_RADIUS,
            circumference_radius,
        )

        angle_step = (
            2.0
            * math.pi
            / node_count
        )

        start_angle = (
            -math.pi
            / 2.0
        )

        for index, node_item in enumerate(
            node_items
        ):

            angle = (
                start_angle
                + index
                * angle_step
            )

            center_x = (
                radius
                * math.cos(
                    angle
                )
            )

            center_y = (
                radius
                * math.sin(
                    angle
                )
            )

            node_x = (
                center_x
                - node_item.NODE_WIDTH
                / 2.0
            )

            node_y = (
                center_y
                - node_item.NODE_HEIGHT
                / 2.0
            )

            node_item.setPos(
                node_x,
                node_y,
            )

        self.update_all_edges()

        self._update_scene_rect()

    def update_all_edges(
        self,
    ) -> None:
        """
        Refresh geometry of all displayed edges.
        """

        for edge_item in self._edge_items:
            edge_item.update_position()

    # ==========================================================
    # Scene bounds
    # ==========================================================

    def graph_bounds(
        self,
    ) -> QRectF:
        """
        Return the bounding rectangle of the displayed graph.
        """

        if not self._node_items:
            return QRectF()

        bounds = QRectF()

        for node_item in self._node_items.values():

            node_bounds = (
                node_item.sceneBoundingRect()
            )

            if bounds.isNull():
                bounds = QRectF(
                    node_bounds
                )

            else:
                bounds = bounds.united(
                    node_bounds
                )

        return bounds

    def _update_scene_rect(
        self,
    ) -> None:
        """
        Resize scene bounds around all graph nodes.
        """

        bounds = self.graph_bounds()

        if bounds.isNull():
            self._reset_scene_rect()
            return

        padded_bounds = bounds.adjusted(
            -self.SCENE_PADDING,
            -self.SCENE_PADDING,
            self.SCENE_PADDING,
            self.SCENE_PADDING,
        )

        minimum_bounds = QRectF(
            -self.DEFAULT_SCENE_WIDTH / 2.0,
            -self.DEFAULT_SCENE_HEIGHT / 2.0,
            self.DEFAULT_SCENE_WIDTH,
            self.DEFAULT_SCENE_HEIGHT,
        )

        self.setSceneRect(
            padded_bounds.united(
                minimum_bounds
            )
        )

    def _reset_scene_rect(
        self,
    ) -> None:
        """
        Restore default empty-scene bounds.
        """

        self.setSceneRect(
            QRectF(
                -self.DEFAULT_SCENE_WIDTH / 2.0,
                -self.DEFAULT_SCENE_HEIGHT / 2.0,
                self.DEFAULT_SCENE_WIDTH,
                self.DEFAULT_SCENE_HEIGHT,
            )
        )

    # ==========================================================
    # Selection
    # ==========================================================

    def _handle_selection_changed(
        self,
    ) -> None:
        """
        Emit a signal describing the current selected item.
        """

        selected_items = (
            self.selectedItems()
        )

        if not selected_items:
            self.selection_cleared.emit()
            return

        selected_item = selected_items[0]

        if isinstance(
            selected_item,
            GraphNodeItem,
        ):

            self.node_selected.emit(
                selected_item
            )

            return

        if isinstance(
            selected_item,
            GraphEdgeItem,
        ):

            self.edge_selected.emit(
                selected_item
            )

    def select_node(
        self,
        entity_id: str,
    ) -> bool:
        """
        Select a node by its entity identifier.
        """

        node_item = self._node_items.get(
            str(
                entity_id
            )
        )

        if node_item is None:
            return False

        self.clearSelection()

        node_item.setSelected(
            True
        )

        return True

    def clear_graph_selection(
        self,
    ) -> None:
        """
        Clear current node or edge selection.
        """

        self.clearSelection()

    # ==========================================================
    # Accessors
    # ==========================================================

    def get_node_item(
        self,
        entity_id: str,
    ) -> GraphNodeItem | None:
        """
        Return a displayed node by identifier.
        """

        return self._node_items.get(
            str(
                entity_id
            )
        )

    def node_items(
        self,
    ) -> tuple[GraphNodeItem, ...]:
        """
        Return all displayed node items.
        """

        return tuple(
            self._node_items.values()
        )

    def edge_items(
        self,
    ) -> tuple[GraphEdgeItem, ...]:
        """
        Return all displayed edge items.
        """

        return tuple(
            self._edge_items
        )

    def graph_data(
        self,
    ) -> dict[str, Any]:
        """
        Return a copy of the currently loaded graph data.
        """

        return {
            "nodes": [
                dict(
                    item
                )
                for item in self._graph_data[
                    "nodes"
                ]
            ],
            "edges": [
                dict(
                    item
                )
                for item in self._graph_data[
                    "edges"
                ]
            ],
            "statistics": dict(
                self._graph_data[
                    "statistics"
                ]
            ),
        }

    def node_count(
        self,
    ) -> int:
        """
        Return the displayed node count.
        """

        return len(
            self._node_items
        )

    def edge_count(
        self,
    ) -> int:
        """
        Return the displayed edge count.
        """

        return len(
            self._edge_items
        )

    # ==========================================================
    # Background
    # ==========================================================

    def drawBackground(
        self,
        painter: QPainter,
        rect: QRectF,
    ) -> None:
        """
        Draw a subtle grid behind graph items.
        """

        super().drawBackground(
            painter,
            rect,
        )

        minor_grid_size = 25
        major_grid_size = 125

        minor_pen = QPen(
            QColor(
                255,
                255,
                255,
                10,
            ),
            1.0,
        )

        major_pen = QPen(
            QColor(
                255,
                255,
                255,
                20,
            ),
            1.0,
        )

        left = (
            math.floor(
                rect.left()
                / minor_grid_size
            )
            * minor_grid_size
        )

        top = (
            math.floor(
                rect.top()
                / minor_grid_size
            )
            * minor_grid_size
        )

        minor_lines = []
        major_lines = []

        x = left

        while x <= rect.right():

            line = (
                x,
                rect.top(),
                x,
                rect.bottom(),
            )

            if (
                int(
                    x
                )
                % major_grid_size
                == 0
            ):
                major_lines.append(
                    line
                )

            else:
                minor_lines.append(
                    line
                )

            x += minor_grid_size

        y = top

        while y <= rect.bottom():

            line = (
                rect.left(),
                y,
                rect.right(),
                y,
            )

            if (
                int(
                    y
                )
                % major_grid_size
                == 0
            ):
                major_lines.append(
                    line
                )

            else:
                minor_lines.append(
                    line
                )

            y += minor_grid_size

        painter.setPen(
            minor_pen
        )

        for (
            x1,
            y1,
            x2,
            y2,
        ) in minor_lines:

            painter.drawLine(
                x1,
                y1,
                x2,
                y2,
            )

        painter.setPen(
            major_pen
        )

        for (
            x1,
            y1,
            x2,
            y2,
        ) in major_lines:

            painter.drawLine(
                x1,
                y1,
                x2,
                y2,
            )