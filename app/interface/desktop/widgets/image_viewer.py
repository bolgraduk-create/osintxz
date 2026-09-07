"""
Image viewer widget.

Responsible for:

- displaying one image
- zooming
- panning
- fitting image to viewport
- showing image at original size
- rotating the displayed image
- exposing viewer state

Does NOT:

- modify the original file
- access database
- process EXIF
- execute OCR
- run AI analysis
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QPoint,
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QImageReader,
    QPixmap,
    QTransform,
    QWheelEvent,
)

from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)


class ImageViewer(
    QGraphicsView,
):
    """
    Interactive image viewer based on QGraphicsView.
    """

    image_loaded = Signal(
        str
    )

    image_cleared = Signal()

    zoom_changed = Signal(
        int
    )

    load_failed = Signal(
        str
    )

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._scene = QGraphicsScene(
            self
        )

        self.setScene(
            self._scene
        )

        self._pixmap_item = QGraphicsPixmapItem()

        self._scene.addItem(
            self._pixmap_item
        )

        self._image_path: Path | None = None

        self._zoom_factor = 1.0

        self._minimum_zoom = 0.05

        self._maximum_zoom = 20.0

        self._zoom_step = 1.20

        self._rotation_angle = 0

        self._fit_mode = True

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
        Configure viewer behavior.
        """

        self.setObjectName(
            "ImageViewer"
        )

        self.setRenderHints(
            self.renderHints()
        )

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
        )

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setBackgroundBrush(
            self.palette().brush(
                self.backgroundRole()
            )
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def load_image(
        self,
        path: str | Path,
    ) -> bool:
        """
        Load one image from disk.
        """

        image_path = Path(
            path
        ).expanduser()

        try:

            image_path = image_path.resolve(
                strict=True
            )

        except FileNotFoundError:

            self.clear_image()

            self.load_failed.emit(
                f"Image file does not exist: {image_path}"
            )

            return False

        if not image_path.is_file():

            self.clear_image()

            self.load_failed.emit(
                f"Path is not a file: {image_path}"
            )

            return False

        reader = QImageReader(
            str(
                image_path
            )
        )

        reader.setAutoTransform(
            True
        )

        image = reader.read()

        if image.isNull():

            self.clear_image()

            error_message = (
                reader.errorString()
                or "Unable to load image."
            )

            self.load_failed.emit(
                error_message
            )

            return False

        pixmap = QPixmap.fromImage(
            image
        )

        if pixmap.isNull():

            self.clear_image()

            self.load_failed.emit(
                "Unable to create image preview."
            )

            return False

        self._image_path = image_path

        self._pixmap_item.setPixmap(
            pixmap
        )

        self._pixmap_item.setTransform(
            QTransform()
        )

        self._scene.setSceneRect(
            self._pixmap_item.boundingRect()
        )

        self._rotation_angle = 0

        self._fit_mode = True

        self.fit_to_window()

        self.image_loaded.emit(
            str(
                image_path
            )
        )

        return True

    def clear_image(
        self,
    ) -> None:
        """
        Clear current image and reset viewer state.
        """

        self.resetTransform()

        self._pixmap_item.setPixmap(
            QPixmap()
        )

        self._pixmap_item.setTransform(
            QTransform()
        )

        self._scene.setSceneRect(
            0.0,
            0.0,
            0.0,
            0.0,
        )

        self._image_path = None

        self._zoom_factor = 1.0

        self._rotation_angle = 0

        self._fit_mode = True

        self.image_cleared.emit()

        self.zoom_changed.emit(
            100
        )

    def fit_to_window(
        self,
    ) -> None:
        """
        Fit the complete image into the viewport.
        """

        if not self.has_image():

            return

        self.resetTransform()

        self.fitInView(
            self._pixmap_item,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        self._fit_mode = True

        self._update_zoom_factor()

    def show_actual_size(
        self,
    ) -> None:
        """
        Display image at 1:1 scale.
        """

        if not self.has_image():

            return

        self.resetTransform()

        self._apply_rotation()

        self._zoom_factor = 1.0

        self._fit_mode = False

        self.zoom_changed.emit(
            100
        )

    def zoom_in(
        self,
    ) -> None:
        """
        Increase image scale.
        """

        self._apply_zoom(
            self._zoom_step
        )

    def zoom_out(
        self,
    ) -> None:
        """
        Decrease image scale.
        """

        self._apply_zoom(
            1.0 / self._zoom_step
        )

    def set_zoom_percent(
        self,
        percent: int,
    ) -> None:
        """
        Set absolute image zoom percentage.
        """

        if not self.has_image():

            return

        normalized_percent = max(
            5,
            min(
                2000,
                int(
                    percent
                ),
            ),
        )

        target_zoom = (
            normalized_percent
            / 100.0
        )

        self.resetTransform()

        self._apply_rotation()

        self.scale(
            target_zoom,
            target_zoom,
        )

        self._zoom_factor = target_zoom

        self._fit_mode = False

        self.zoom_changed.emit(
            normalized_percent
        )

    def rotate_left(
        self,
    ) -> None:
        """
        Rotate displayed image 90 degrees left.
        """

        self._rotate(
            -90
        )

    def rotate_right(
        self,
    ) -> None:
        """
        Rotate displayed image 90 degrees right.
        """

        self._rotate(
            90
        )

    def reset_view(
        self,
    ) -> None:
        """
        Reset rotation and fit image into viewport.
        """

        if not self.has_image():

            return

        self._rotation_angle = 0

        self._pixmap_item.setTransform(
            QTransform()
        )

        self.fit_to_window()

    def has_image(
        self,
    ) -> bool:
        """
        Return True when an image is loaded.
        """

        return (
            not self._pixmap_item
            .pixmap()
            .isNull()
        )

    def image_path(
        self,
    ) -> str | None:
        """
        Return loaded image path.
        """

        if self._image_path is None:

            return None

        return str(
            self._image_path
        )

    def zoom_percent(
        self,
    ) -> int:
        """
        Return current zoom percentage.
        """

        return int(
            round(
                self._zoom_factor
                * 100
            )
        )

    def rotation_angle(
        self,
    ) -> int:
        """
        Return current display rotation.
        """

        return self._rotation_angle

    # ==========================================================
    # Zoom
    # ==========================================================

    def _apply_zoom(
        self,
        factor: float,
    ) -> None:
        """
        Apply relative zoom.
        """

        if not self.has_image():

            return

        target_zoom = (
            self._zoom_factor
            * factor
        )

        if target_zoom < self._minimum_zoom:

            factor = (
                self._minimum_zoom
                / self._zoom_factor
            )

            target_zoom = self._minimum_zoom

        elif target_zoom > self._maximum_zoom:

            factor = (
                self._maximum_zoom
                / self._zoom_factor
            )

            target_zoom = self._maximum_zoom

        self.scale(
            factor,
            factor,
        )

        self._zoom_factor = target_zoom

        self._fit_mode = False

        self.zoom_changed.emit(
            self.zoom_percent()
        )

    def _update_zoom_factor(
        self,
    ) -> None:
        """
        Read current scale from the view transform.
        """

        transform = self.transform()

        horizontal_scale = abs(
            transform.m11()
        )

        vertical_scale = abs(
            transform.m22()
        )

        scale_value = max(
            horizontal_scale,
            vertical_scale,
        )

        if scale_value <= 0:

            scale_value = 1.0

        self._zoom_factor = scale_value

        self.zoom_changed.emit(
            self.zoom_percent()
        )

    # ==========================================================
    # Rotation
    # ==========================================================

    def _rotate(
        self,
        angle: int,
    ) -> None:
        """
        Rotate image display.
        """

        if not self.has_image():

            return

        self._rotation_angle = (
            self._rotation_angle
            + angle
        ) % 360

        self._pixmap_item.setTransform(
            QTransform()
        )

        self._apply_rotation()

        self._scene.setSceneRect(
            self._pixmap_item
            .sceneBoundingRect()
        )

        if self._fit_mode:

            self.fit_to_window()

    def _apply_rotation(
        self,
    ) -> None:
        """
        Apply current rotation to pixmap item.
        """

        pixmap = (
            self._pixmap_item
            .pixmap()
        )

        if pixmap.isNull():

            return

        center_x = (
            pixmap.width()
            / 2.0
        )

        center_y = (
            pixmap.height()
            / 2.0
        )

        transform = QTransform()

        transform.translate(
            center_x,
            center_y,
        )

        transform.rotate(
            self._rotation_angle
        )

        transform.translate(
            -center_x,
            -center_y,
        )

        self._pixmap_item.setTransform(
            transform
        )

    # ==========================================================
    # Events
    # ==========================================================

    def wheelEvent(
        self,
        event: QWheelEvent,
    ) -> None:
        """
        Zoom with Ctrl + mouse wheel.

        Normal wheel behavior remains available for scrolling.
        """

        if (
            event.modifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):

            if event.angleDelta().y() > 0:

                self.zoom_in()

            else:

                self.zoom_out()

            event.accept()

            return

        super().wheelEvent(
            event
        )

    def mousePressEvent(
        self,
        event,
    ) -> None:
        """
        Start panning with middle mouse button.
        """

        if (
            event.button()
            == Qt.MouseButton.MiddleButton
            and self.has_image()
        ):

            self._is_panning = True

            self._pan_start = (
                event.position()
                .toPoint()
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
        event,
    ) -> None:
        """
        Pan image while middle mouse button is held.
        """

        if self._is_panning:

            current_position = (
                event.position()
                .toPoint()
            )

            delta = (
                current_position
                - self._pan_start
            )

            self._pan_start = (
                current_position
            )

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value()
                - delta.x()
            )

            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value()
                - delta.y()
            )

            event.accept()

            return

        super().mouseMoveEvent(
            event
        )

    def mouseReleaseEvent(
        self,
        event,
    ) -> None:
        """
        Finish image panning.
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

    def resizeEvent(
        self,
        event,
    ) -> None:
        """
        Keep fitted images fitted after resizing.
        """

        super().resizeEvent(
            event
        )

        if (
            self._fit_mode
            and self.has_image()
        ):

            self.fit_to_window()