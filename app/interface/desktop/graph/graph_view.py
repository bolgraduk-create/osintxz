"""
Graph graphics view.

Responsible for:

- displaying GraphScene
- zooming with the mouse wheel
- panning with the middle mouse button
- fitting the complete graph into the viewport
- resetting zoom
- centering selected graph items

Does NOT:

- access the database
- load graph data from services
- create application controllers
- execute graph analysis
"""

from __future__ import annotations

from PySide6.QtCore import (
    QPoint,
    QPointF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsView,
)

from app.interface.desktop.graph.graph_scene import (
    GraphScene,
)


class GraphView(QGraphicsView):
    """
    Interactive viewport for an entity graph scene.
    """

    zoom_changed = Signal(
        float,
    )

    MINIMUM_ZOOM = 0.18
    MAXIMUM_ZOOM = 4.0

    ZOOM_STEP = 1.15

    def __init__(
        self,
        scene: GraphScene | None = None,
        parent=None,
    ) -> None:

        graph_scene = (
            scene
            if scene is not None
            else GraphScene()
        )

        super().__init__(
            graph_scene,
            parent,
        )

        self._is_panning = False
        self._pan_start = QPoint()

        self._setup_view()

    # ==========================================================
    # Setup
    # ==========================================================

    def _setup_view(
        self,
    ) -> None:
        """
        Configure graph rendering and viewport behavior.
        """

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )

        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )

        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontSavePainterState,
            True,
        )

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        self.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag
        )

        self.setRubberBandSelectionMode(
            Qt.ItemSelectionMode.IntersectsItemShape
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.setMouseTracking(
            True
        )

    # ==========================================================
    # Scene access
    # ==========================================================

    def graph_scene(
        self,
    ) -> GraphScene:
        """
        Return the current graph scene.
        """

        scene = self.scene()

        if not isinstance(
            scene,
            GraphScene,
        ):
            raise TypeError(
                "GraphView requires GraphScene."
            )

        return scene

    # ==========================================================
    # Zoom
    # ==========================================================

    def current_zoom(
        self,
    ) -> float:
        """
        Return the current horizontal zoom factor.
        """

        return float(
            self.transform().m11()
        )

    def zoom_in(
        self,
    ) -> None:
        """
        Increase graph zoom.
        """

        self._apply_zoom_factor(
            self.ZOOM_STEP
        )

    def zoom_out(
        self,
    ) -> None:
        """
        Decrease graph zoom.
        """

        self._apply_zoom_factor(
            1.0
            / self.ZOOM_STEP
        )

    def reset_zoom(
        self,
    ) -> None:
        """
        Reset transform while keeping the current scene center.
        """

        scene_center = self.mapToScene(
            self.viewport().rect().center()
        )

        self.resetTransform()

        self.centerOn(
            scene_center
        )

        self.zoom_changed.emit(
            self.current_zoom()
        )

    def _apply_zoom_factor(
        self,
        factor: float,
    ) -> None:
        """
        Apply a bounded scale factor.
        """

        current_zoom = self.current_zoom()

        target_zoom = (
            current_zoom
            * factor
        )

        if (
            target_zoom
            < self.MINIMUM_ZOOM
        ):
            factor = (
                self.MINIMUM_ZOOM
                / current_zoom
            )

        elif (
            target_zoom
            > self.MAXIMUM_ZOOM
        ):
            factor = (
                self.MAXIMUM_ZOOM
                / current_zoom
            )

        if abs(
            factor - 1.0
        ) < 0.000001:
            return

        self.scale(
            factor,
            factor,
        )

        self.zoom_changed.emit(
            self.current_zoom()
        )

    # ==========================================================
    # Fitting and centering
    # ==========================================================

    def fit_graph(
        self,
    ) -> None:
        """
        Fit every graph node into the viewport.
        """

        bounds = (
            self.graph_scene().graph_bounds()
        )

        if bounds.isNull():
            self.resetTransform()

            self.centerOn(
                QPointF(
                    0.0,
                    0.0,
                )
            )

            self.zoom_changed.emit(
                self.current_zoom()
            )

            return

        padded_bounds = bounds.adjusted(
            -80.0,
            -80.0,
            80.0,
            80.0,
        )

        self.fitInView(
            padded_bounds,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        current_zoom = self.current_zoom()

        if (
            current_zoom
            > self.MAXIMUM_ZOOM
        ):
            correction = (
                self.MAXIMUM_ZOOM
                / current_zoom
            )

            self.scale(
                correction,
                correction,
            )

        elif (
            current_zoom
            < self.MINIMUM_ZOOM
        ):
            correction = (
                self.MINIMUM_ZOOM
                / current_zoom
            )

            self.scale(
                correction,
                correction,
            )

        self.centerOn(
            bounds.center()
        )

        self.zoom_changed.emit(
            self.current_zoom()
        )

    def center_on_item(
        self,
        item: QGraphicsItem,
    ) -> None:
        """
        Center the viewport on a graph item.
        """

        self.centerOn(
            item
        )

    def center_on_selected_item(
        self,
    ) -> bool:
        """
        Center on the first selected graph item.
        """

        selected_items = (
            self.graph_scene().selectedItems()
        )

        if not selected_items:
            return False

        self.center_on_item(
            selected_items[0]
        )

        return True

    # ==========================================================
    # Events
    # ==========================================================

    def wheelEvent(
        self,
        event: QWheelEvent,
    ) -> None:
        """
        Zoom the graph with the mouse wheel.
        """

        if (
            event.angleDelta().y()
            > 0
        ):
            self.zoom_in()

        elif (
            event.angleDelta().y()
            < 0
        ):
            self.zoom_out()

        event.accept()

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """
        Start viewport panning with the middle mouse button.
        """

        if (
            event.button()
            == Qt.MouseButton.MiddleButton
        ):
            self._is_panning = True

            self._pan_start = (
                event.position().toPoint()
            )

            self.setCursor(
                Qt.CursorShape.ClosedHandCursor
            )

            event.accept()

            return

        super().mousePressEvent(
            event
        )

    def mouseMoveEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """
        Pan the viewport while the middle button is held.
        """

        if self._is_panning:

            current_position = (
                event.position().toPoint()
            )

            delta = (
                current_position
                - self._pan_start
            )

            self._pan_start = (
                current_position
            )

            horizontal_bar = (
                self.horizontalScrollBar()
            )

            vertical_bar = (
                self.verticalScrollBar()
            )

            horizontal_bar.setValue(
                horizontal_bar.value()
                - delta.x()
            )

            vertical_bar.setValue(
                vertical_bar.value()
                - delta.y()
            )

            event.accept()

            return

        super().mouseMoveEvent(
            event
        )

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        """
        Stop viewport panning.
        """

        if (
            event.button()
            == Qt.MouseButton.MiddleButton
            and self._is_panning
        ):
            self._is_panning = False

            self.unsetCursor()

            event.accept()

            return

        super().mouseReleaseEvent(
            event
        )

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
        """
        Handle basic graph navigation shortcuts.
        """

        if (
            event.key()
            == Qt.Key.Key_Plus
            or event.key()
            == Qt.Key.Key_Equal
        ):
            self.zoom_in()

            event.accept()

            return

        if (
            event.key()
            == Qt.Key.Key_Minus
        ):
            self.zoom_out()

            event.accept()

            return

        if (
            event.key()
            == Qt.Key.Key_0
        ):
            self.fit_graph()

            event.accept()

            return

        if (
            event.key()
            == Qt.Key.Key_Home
        ):
            self.center_on_selected_item()

            event.accept()

            return

        if (
            event.key()
            == Qt.Key.Key_Escape
        ):
            self.graph_scene().clear_graph_selection()

            event.accept()

            return

        super().keyPressEvent(
            event
        )