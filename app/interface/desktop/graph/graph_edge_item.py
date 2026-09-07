"""
Graph edge graphics item.

Responsible for:

- displaying a relationship between two nodes
- updating its geometry when nodes move
- drawing relationship labels
- supporting selection highlighting

Does NOT:

- access the database
- load graph data
- execute graph analysis
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from app.interface.desktop.graph.graph_node_item import GraphNodeItem


class GraphEdgeItem(QGraphicsLineItem):
    """
    Visual connection between two graph nodes.
    """

    def __init__(
        self,
        source: GraphNodeItem,
        target: GraphNodeItem,
        relationship_type: str,
        confidence: float = 1.0,
        parent: QGraphicsItem | None = None,
    ) -> None:

        super().__init__(parent)

        self.source = source
        self.target = target

        self.relationship_type = relationship_type
        self.confidence = confidence

        self.normal_pen = QPen(
            QColor("#7f8c99"),
            2.0,
        )

        self.selected_pen = QPen(
            QColor("#4da3ff"),
            3.0,
        )

        self.setPen(self.normal_pen)

        self.setZValue(1)

        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
            True,
        )

        self.source.add_edge(self)
        self.target.add_edge(self)

        self.update_position()

    # ======================================================
    # Geometry
    # ======================================================

    def update_position(
        self,
    ) -> None:
        """
        Recalculate line coordinates.
        """

        self.setLine(
            self.source.center_position().x(),
            self.source.center_position().y(),
            self.target.center_position().x(),
            self.target.center_position().y(),
        )

    # ======================================================
    # Painting
    # ======================================================

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:

        if self.isSelected():
            self.setPen(self.selected_pen)
        else:
            self.setPen(self.normal_pen)

        super().paint(
            painter,
            option,
            widget,
        )

        painter.save()

        painter.setFont(
            QFont(
                painter.font().family(),
                8,
            )
        )

        painter.setPen(
            QColor("#cfd6df")
        )

        midpoint = QPointF(
            (
                self.line().x1()
                + self.line().x2()
            )
            / 2,
            (
                self.line().y1()
                + self.line().y2()
            )
            / 2,
        )

        painter.drawText(
            midpoint,
            self.relationship_type.replace(
                "_",
                " ",
            ),
        )

        painter.restore()

    # ======================================================
    # Cleanup
    # ======================================================

    def detach(
        self,
    ) -> None:
        """
        Disconnect edge from nodes.
        """

        self.source.remove_edge(self)
        self.target.remove_edge(self)