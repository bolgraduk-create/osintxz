"""
Graph node graphics item.

Responsible for:

- displaying a single graph node
- displaying the node label
- displaying the entity type
- supporting selection
- supporting manual dragging
- notifying connected edges when moved

Does NOT:

- access the database
- load graph data
- execute graph analysis
- manage the graphics scene
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
)

from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)

from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QStyle,
    QStyleOptionGraphicsItem,
    QWidget,
)

if TYPE_CHECKING:
    from app.interface.desktop.graph.graph_edge_item import (
        GraphEdgeItem,
    )


class GraphNodeItem(QGraphicsObject):
    """
    Interactive entity node displayed inside a graph scene.
    """

    NODE_WIDTH = 170.0
    NODE_HEIGHT = 68.0
    NODE_RADIUS = 12.0

    TYPE_BADGE_HEIGHT = 20.0

    def __init__(
        self,
        entity_id: UUID | str,
        label: str,
        entity_type: str,
        degree: int = 0,
        parent: QGraphicsItem | None = None,
    ) -> None:

        super().__init__(
            parent,
        )

        self.entity_id = str(
            entity_id
        )

        self.label = (
            label.strip()
            if label
            else "Unknown entity"
        )

        self.entity_type = (
            entity_type.strip()
            if entity_type
            else "unknown"
        )

        self.degree = max(
            int(degree),
            0,
        )

        self._edges: list[
            GraphEdgeItem
        ] = []

        self._normal_background = QColor(
            "#202936"
        )

        self._hover_background = QColor(
            "#293647"
        )

        self._selected_background = QColor(
            "#33455c"
        )

        self._border_color = QColor(
            "#53657a"
        )

        self._selected_border_color = QColor(
            "#4da3ff"
        )

        self._text_color = QColor(
            "#f4f7fb"
        )

        self._secondary_text_color = QColor(
            "#aebdcd"
        )

        self._badge_color = self._get_type_color(
            self.entity_type
        )

        self._is_hovered = False

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self.setAcceptHoverEvents(
            True
        )

        self.setCursor(
            Qt.CursorShape.OpenHandCursor
        )

        self.setZValue(
            10.0
        )

        self.setToolTip(
            self._build_tooltip()
        )

    # ==========================================================
    # Geometry
    # ==========================================================

    def boundingRect(
        self,
    ) -> QRectF:
        """
        Return the complete node drawing rectangle.
        """

        return QRectF(
            0.0,
            0.0,
            self.NODE_WIDTH,
            self.NODE_HEIGHT,
        )

    def shape(
        self,
    ) -> QPainterPath:
        """
        Return rounded node shape for precise selection.
        """

        path = QPainterPath()

        path.addRoundedRect(
            self.boundingRect(),
            self.NODE_RADIUS,
            self.NODE_RADIUS,
        )

        return path

    def center_position(
        self,
    ) -> QPointF:
        """
        Return the node center in scene coordinates.
        """

        return self.mapToScene(
            self.boundingRect().center()
        )

    # ==========================================================
    # Painting
    # ==========================================================

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        """
        Draw the node.
        """

        del widget

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        node_rect = self.boundingRect()

        background_color = (
            self._normal_background
        )

        if self.isSelected():
            background_color = (
                self._selected_background
            )

        elif self._is_hovered:
            background_color = (
                self._hover_background
            )

        border_color = (
            self._selected_border_color
            if self.isSelected()
            else self._border_color
        )

        border_width = (
            2.0
            if self.isSelected()
            else 1.0
        )

        painter.setPen(
            QPen(
                border_color,
                border_width,
            )
        )

        painter.setBrush(
            QBrush(
                background_color
            )
        )

        painter.drawRoundedRect(
            node_rect,
            self.NODE_RADIUS,
            self.NODE_RADIUS,
        )

        self._paint_type_indicator(
            painter
        )

        self._paint_label(
            painter
        )

        self._paint_metadata(
            painter
        )

        if (
            option.state
            & QStyle.StateFlag.State_HasFocus
        ):
            self._paint_focus_outline(
                painter
            )

    def _paint_type_indicator(
        self,
        painter: QPainter,
    ) -> None:
        """
        Draw entity-type indicator on the left side.
        """

        indicator_rect = QRectF(
            0.0,
            0.0,
            6.0,
            self.NODE_HEIGHT,
        )

        painter.save()

        indicator_path = QPainterPath()

        indicator_path.addRoundedRect(
            indicator_rect,
            self.NODE_RADIUS,
            self.NODE_RADIUS,
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QBrush(
                self._badge_color
            )
        )

        painter.drawPath(
            indicator_path
        )

        painter.restore()

    def _paint_label(
        self,
        painter: QPainter,
    ) -> None:
        """
        Draw primary entity label.
        """

        label_rect = QRectF(
            18.0,
            9.0,
            self.NODE_WIDTH - 30.0,
            26.0,
        )

        font = QFont(
            painter.font()
        )

        font.setPointSize(
            10
        )

        font.setWeight(
            QFont.Weight.DemiBold
        )

        painter.setFont(
            font
        )

        painter.setPen(
            QPen(
                self._text_color
            )
        )

        label_metrics = (
            painter.fontMetrics()
        )

        display_label = (
            label_metrics.elidedText(
                self.label,
                Qt.TextElideMode.ElideRight,
                int(
                    label_rect.width()
                ),
            )
        )

        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            display_label,
        )

    def _paint_metadata(
        self,
        painter: QPainter,
    ) -> None:
        """
        Draw entity type and connection count.
        """

        metadata_rect = QRectF(
            18.0,
            36.0,
            self.NODE_WIDTH - 30.0,
            22.0,
        )

        font = QFont(
            painter.font()
        )

        font.setPointSize(
            8
        )

        font.setWeight(
            QFont.Weight.Normal
        )

        painter.setFont(
            font
        )

        painter.setPen(
            QPen(
                self._secondary_text_color
            )
        )

        entity_type = (
            self.entity_type.replace(
                "_",
                " ",
            ).title()
        )

        connections_text = (
            f"{self.degree} connections"
            if self.degree != 1
            else "1 connection"
        )

        metadata_text = (
            f"{entity_type}  •  "
            f"{connections_text}"
        )

        metrics = painter.fontMetrics()

        display_text = (
            metrics.elidedText(
                metadata_text,
                Qt.TextElideMode.ElideRight,
                int(
                    metadata_rect.width()
                ),
            )
        )

        painter.drawText(
            metadata_rect,
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            display_text,
        )

    def _paint_focus_outline(
        self,
        painter: QPainter,
    ) -> None:
        """
        Draw keyboard-focus outline.
        """

        focus_rect = (
            self.boundingRect().adjusted(
                3.0,
                3.0,
                -3.0,
                -3.0,
            )
        )

        focus_pen = QPen(
            self._selected_border_color,
            1.0,
            Qt.PenStyle.DotLine,
        )

        painter.setPen(
            focus_pen
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        painter.drawRoundedRect(
            focus_rect,
            self.NODE_RADIUS - 2.0,
            self.NODE_RADIUS - 2.0,
        )

    # ==========================================================
    # Edge management
    # ==========================================================

    def add_edge(
        self,
        edge: GraphEdgeItem,
    ) -> None:
        """
        Register an edge connected to this node.
        """

        if edge not in self._edges:
            self._edges.append(
                edge
            )

    def remove_edge(
        self,
        edge: GraphEdgeItem,
    ) -> None:
        """
        Unregister a connected edge.
        """

        if edge in self._edges:
            self._edges.remove(
                edge
            )

    def update_edges(
        self,
    ) -> None:
        """
        Update geometry of every connected edge.
        """

        for edge in tuple(
            self._edges
        ):
            edge.update_position()

    def connected_edges(
        self,
    ) -> tuple[GraphEdgeItem, ...]:
        """
        Return connected edges without exposing mutable storage.
        """

        return tuple(
            self._edges
        )

    # ==========================================================
    # Item events
    # ==========================================================

    def itemChange(
        self,
        change: QGraphicsItem.GraphicsItemChange,
        value: object,
    ) -> object:
        """
        React to position and selection changes.
        """

        if (
            change
            == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
        ):
            self.update_edges()

        elif (
            change
            == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged
        ):
            self.update()

        return super().itemChange(
            change,
            value,
        )

    def hoverEnterEvent(
        self,
        event,
    ) -> None:
        """
        Activate hover appearance.
        """

        self._is_hovered = True

        self.setCursor(
            Qt.CursorShape.OpenHandCursor
        )

        self.update()

        super().hoverEnterEvent(
            event
        )

    def hoverLeaveEvent(
        self,
        event,
    ) -> None:
        """
        Restore normal appearance.
        """

        self._is_hovered = False

        self.update()

        super().hoverLeaveEvent(
            event
        )

    def mousePressEvent(
        self,
        event,
    ) -> None:
        """
        Change cursor while dragging.
        """

        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.setCursor(
                Qt.CursorShape.ClosedHandCursor
            )

        super().mousePressEvent(
            event
        )

    def mouseReleaseEvent(
        self,
        event,
    ) -> None:
        """
        Restore cursor after dragging.
        """

        self.setCursor(
            Qt.CursorShape.OpenHandCursor
        )

        super().mouseReleaseEvent(
            event
        )

    # ==========================================================
    # Data updates
    # ==========================================================

    def set_degree(
        self,
        degree: int,
    ) -> None:
        """
        Update displayed connection count.
        """

        normalized_degree = max(
            int(degree),
            0,
        )

        if normalized_degree == self.degree:
            return

        self.degree = normalized_degree

        self.setToolTip(
            self._build_tooltip()
        )

        self.update()

    def set_label(
        self,
        label: str,
    ) -> None:
        """
        Update entity label.
        """

        normalized_label = (
            label.strip()
            if label
            else "Unknown entity"
        )

        if normalized_label == self.label:
            return

        self.label = normalized_label

        self.setToolTip(
            self._build_tooltip()
        )

        self.update()

    # ==========================================================
    # Helpers
    # ==========================================================

    def _build_tooltip(
        self,
    ) -> str:
        """
        Build text shown when the pointer stays over a node.
        """

        entity_type = (
            self.entity_type.replace(
                "_",
                " ",
            ).title()
        )

        return (
            f"{self.label}\n"
            f"Type: {entity_type}\n"
            f"Connections: {self.degree}"
        )

    @staticmethod
    def _get_type_color(
        entity_type: str,
    ) -> QColor:
        """
        Return an indicator color for an entity type.
        """

        normalized_type = (
            entity_type.strip()
            .lower()
            .replace(
                "-",
                "_",
            )
            .replace(
                " ",
                "_",
            )
        )

        type_colors = {
            "person": "#4da3ff",
            "organization": "#b07cff",
            "company": "#b07cff",
            "username": "#3ecf8e",
            "account": "#3ecf8e",
            "email": "#f0a84b",
            "phone": "#ef6c78",
            "phone_number": "#ef6c78",
            "domain": "#45c3d3",
            "website": "#45c3d3",
            "url": "#45c3d3",
            "ip": "#d58a45",
            "ip_address": "#d58a45",
            "location": "#e072c4",
            "address": "#e072c4",
            "file": "#9aa8b8",
            "document": "#9aa8b8",
            "message": "#7f9cf5",
            "unknown": "#7b8794",
        }

        return QColor(
            type_colors.get(
                normalized_type,
                "#7b8794",
            )
        )