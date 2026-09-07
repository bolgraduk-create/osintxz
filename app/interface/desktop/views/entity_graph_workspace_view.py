"""
Entity graph workspace view.

Responsible for:

- displaying the investigation entity graph
- displaying graph statistics
- providing graph navigation controls
- searching and selecting graph nodes
- displaying selected node or edge details
- reacting to application language changes

Does NOT:

- access the database
- call repositories
- execute graph analysis
- build graph domain data
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    Qt,
    QTimer,
)

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.graph.graph_edge_item import (
    GraphEdgeItem,
)

from app.interface.desktop.graph.graph_node_item import (
    GraphNodeItem,
)

from app.interface.desktop.graph.graph_scene import (
    GraphScene,
)

from app.interface.desktop.graph.graph_view import (
    GraphView,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class EntityGraphWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Workspace tab for investigation entity graph.

    The view automatically updates all visible interface text
    when the active application language changes.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent,
        )

        self._graph_data: dict[str, Any] = {
            "nodes": [],
            "edges": [],
            "statistics": {},
        }

        self._search_results: list[
            GraphNodeItem
        ] = []

        self._search_result_index = -1

        self._selected_node: (
            GraphNodeItem | None
        ) = None

        self._selected_edge: (
            GraphEdgeItem | None
        ) = None

        self._setup_ui()
        self._connect_signals()
        self._apply_styles()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

        self._update_statistics()
        self._show_empty_details()
        self._update_graph_status()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create graph workspace interface.
        """

        self.setObjectName(
            "EntityGraphWorkspaceView"
        )

        self.root_layout = QVBoxLayout(
            self,
        )

        self.root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.root_layout.setSpacing(
            0,
        )

        self._create_toolbar()
        self._create_statistics_bar()
        self._create_workspace_splitter()

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create graph toolbar.
        """

        self.toolbar = QFrame(
            self
        )

        self.toolbar.setObjectName(
            "graphToolbar"
        )

        self.toolbar_layout = QHBoxLayout(
            self.toolbar,
        )

        self.toolbar_layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        self.toolbar_layout.setSpacing(
            8,
        )

        self.title = QLabel(
            "Entity Graph",
            self.toolbar,
        )

        self.title.setObjectName(
            "graphTitle"
        )

        self.toolbar_layout.addWidget(
            self.title
        )

        self.toolbar_layout.addSpacing(
            10
        )

        self.search_input = QLineEdit(
            self.toolbar
        )

        self.search_input.setObjectName(
            "graphSearchInput"
        )

        self.search_input.setPlaceholderText(
            "Search entities..."
        )

        self.search_input.setClearButtonEnabled(
            True
        )

        self.search_input.setMinimumWidth(
            220
        )

        self.toolbar_layout.addWidget(
            self.search_input
        )

        self.search_button = QPushButton(
            "Search",
            self.toolbar,
        )

        self.search_button.setObjectName(
            "graphToolbarButton"
        )

        self.toolbar_layout.addWidget(
            self.search_button
        )

        self.next_result_button = QPushButton(
            "Next",
            self.toolbar,
        )

        self.next_result_button.setObjectName(
            "graphToolbarButton"
        )

        self.next_result_button.setEnabled(
            False
        )

        self.toolbar_layout.addWidget(
            self.next_result_button
        )

        self.toolbar_layout.addStretch(
            1
        )

        self.layout_selector = QComboBox(
            self.toolbar
        )

        self.layout_selector.setObjectName(
            "graphLayoutSelector"
        )

        self.layout_selector.addItem(
            "Circular",
            "circular",
        )

        self.layout_selector.setMinimumWidth(
            120
        )

        self.toolbar_layout.addWidget(
            self.layout_selector
        )

        self.layout_button = QPushButton(
            "Apply Layout",
            self.toolbar,
        )

        self.layout_button.setObjectName(
            "graphToolbarButton"
        )

        self.toolbar_layout.addWidget(
            self.layout_button
        )

        self.zoom_out_button = QPushButton(
            "−",
            self.toolbar,
        )

        self.zoom_out_button.setObjectName(
            "graphZoomButton"
        )

        self.zoom_out_button.setToolTip(
            "Zoom out"
        )

        self.toolbar_layout.addWidget(
            self.zoom_out_button
        )

        self.zoom_label = QLabel(
            "100%",
            self.toolbar,
        )

        self.zoom_label.setObjectName(
            "graphZoomLabel"
        )

        self.zoom_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.zoom_label.setMinimumWidth(
            52
        )

        self.toolbar_layout.addWidget(
            self.zoom_label
        )

        self.zoom_in_button = QPushButton(
            "+",
            self.toolbar,
        )

        self.zoom_in_button.setObjectName(
            "graphZoomButton"
        )

        self.zoom_in_button.setToolTip(
            "Zoom in"
        )

        self.toolbar_layout.addWidget(
            self.zoom_in_button
        )

        self.fit_button = QPushButton(
            "Fit",
            self.toolbar,
        )

        self.fit_button.setObjectName(
            "graphToolbarButton"
        )

        self.fit_button.setToolTip(
            "Fit complete graph into the viewport"
        )

        self.toolbar_layout.addWidget(
            self.fit_button
        )

        self.root_layout.addWidget(
            self.toolbar
        )

    def _create_statistics_bar(
        self,
    ) -> None:
        """
        Create graph statistics bar.
        """

        self.statistics_bar = QFrame(
            self
        )

        self.statistics_bar.setObjectName(
            "graphStatisticsBar"
        )

        self.statistics_layout = QHBoxLayout(
            self.statistics_bar,
        )

        self.statistics_layout.setContentsMargins(
            14,
            8,
            14,
            8,
        )

        self.statistics_layout.setSpacing(
            22,
        )

        self.node_count_label = QLabel(
            "Nodes: 0",
            self.statistics_bar,
        )

        self.edge_count_label = QLabel(
            "Edges: 0",
            self.statistics_bar,
        )

        self.connected_count_label = QLabel(
            "Connected: 0",
            self.statistics_bar,
        )

        self.isolated_count_label = QLabel(
            "Isolated: 0",
            self.statistics_bar,
        )

        self.density_label = QLabel(
            "Density: 0",
            self.statistics_bar,
        )

        for label in (
            self.node_count_label,
            self.edge_count_label,
            self.connected_count_label,
            self.isolated_count_label,
            self.density_label,
        ):

            label.setObjectName(
                "graphStatisticLabel"
            )

            self.statistics_layout.addWidget(
                label
            )

        self.statistics_layout.addStretch(
            1
        )

        self.status_label = QLabel(
            "No graph loaded",
            self.statistics_bar,
        )

        self.status_label.setObjectName(
            "graphStatusLabel"
        )

        self.statistics_layout.addWidget(
            self.status_label
        )

        self.root_layout.addWidget(
            self.statistics_bar
        )

    def _create_workspace_splitter(
        self,
    ) -> None:
        """
        Create graph and details workspace.
        """

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )

        self.splitter.setObjectName(
            "graphSplitter"
        )

        self.splitter.setChildrenCollapsible(
            False
        )

        self._create_graph_panel()
        self._create_details_panel()

        self.splitter.addWidget(
            self.graph_container
        )

        self.splitter.addWidget(
            self.details_panel
        )

        self.splitter.setStretchFactor(
            0,
            1,
        )

        self.splitter.setStretchFactor(
            1,
            0,
        )

        self.splitter.setSizes(
            [
                900,
                300,
            ]
        )

        self.root_layout.addWidget(
            self.splitter,
            1,
        )

    def _create_graph_panel(
        self,
    ) -> None:
        """
        Create graph visualization panel.
        """

        self.graph_container = QFrame(
            self.splitter
        )

        self.graph_container.setObjectName(
            "graphContainer"
        )

        self.graph_layout = QVBoxLayout(
            self.graph_container,
        )

        self.graph_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.graph_layout.setSpacing(
            0
        )

        self.scene = GraphScene(
            self
        )

        self.graph_view = GraphView(
            scene=self.scene,
            parent=self.graph_container,
        )

        self.graph_layout.addWidget(
            self.graph_view
        )

    def _create_details_panel(
        self,
    ) -> None:
        """
        Create selection details panel.
        """

        self.details_panel = QFrame(
            self.splitter
        )

        self.details_panel.setObjectName(
            "graphDetailsPanel"
        )

        self.details_panel.setMinimumWidth(
            260
        )

        self.details_panel.setMaximumWidth(
            420
        )

        self.details_layout = QVBoxLayout(
            self.details_panel,
        )

        self.details_layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        self.details_layout.setSpacing(
            12
        )

        self.details_title = QLabel(
            "Selection",
            self.details_panel,
        )

        self.details_title.setObjectName(
            "graphDetailsTitle"
        )

        self.details_layout.addWidget(
            self.details_title
        )

        self.details_type_label = QLabel(
            "",
            self.details_panel,
        )

        self.details_type_label.setObjectName(
            "graphDetailsType"
        )

        self.details_type_label.setWordWrap(
            True
        )

        self.details_layout.addWidget(
            self.details_type_label
        )

        self.details_body = QLabel(
            "",
            self.details_panel,
        )

        self.details_body.setObjectName(
            "graphDetailsBody"
        )

        self.details_body.setWordWrap(
            True
        )

        self.details_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.details_body.setAlignment(
            Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft
        )

        self.details_body.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.details_layout.addWidget(
            self.details_body,
            1,
        )

        self.center_selected_button = QPushButton(
            "Center selected",
            self.details_panel,
        )

        self.center_selected_button.setObjectName(
            "graphPrimaryButton"
        )

        self.center_selected_button.setEnabled(
            False
        )

        self.details_layout.addWidget(
            self.center_selected_button
        )

        self.clear_selection_button = QPushButton(
            "Clear selection",
            self.details_panel,
        )

        self.clear_selection_button.setObjectName(
            "graphSecondaryButton"
        )

        self.clear_selection_button.setEnabled(
            False
        )

        self.details_layout.addWidget(
            self.clear_selection_button
        )

    # ==========================================================
    # Signals
    # ==========================================================

    def _connect_signals(
        self,
    ) -> None:
        """
        Connect graph controls and scene events.
        """

        self.zoom_in_button.clicked.connect(
            self.graph_view.zoom_in
        )

        self.zoom_out_button.clicked.connect(
            self.graph_view.zoom_out
        )

        self.fit_button.clicked.connect(
            self.graph_view.fit_graph
        )

        self.layout_button.clicked.connect(
            self._apply_selected_layout
        )

        self.search_button.clicked.connect(
            self._search_nodes
        )

        self.next_result_button.clicked.connect(
            self._select_next_search_result
        )

        self.search_input.returnPressed.connect(
            self._search_nodes
        )

        self.search_input.textChanged.connect(
            self._handle_search_text_changed
        )

        self.center_selected_button.clicked.connect(
            self.graph_view.center_on_selected_item
        )

        self.clear_selection_button.clicked.connect(
            self.scene.clear_graph_selection
        )

        self.graph_view.zoom_changed.connect(
            self._update_zoom_label
        )

        self.scene.node_selected.connect(
            self._show_node_details
        )

        self.scene.edge_selected.connect(
            self._show_edge_details
        )

        self.scene.selection_cleared.connect(
            self._show_empty_details
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        self.title.setText(
            self.translate(
                "entity_graph.title",
                default="Entity Graph",
            )
        )

        self.search_input.setPlaceholderText(
            self.translate(
                "entity_graph.search.placeholder",
                default="Search entities...",
            )
        )

        self.search_button.setText(
            self.translate(
                "entity_graph.search.button",
                default="Search",
            )
        )

        self.next_result_button.setText(
            self.translate(
                "entity_graph.search.next",
                default="Next",
            )
        )

        current_layout_data = (
            self.layout_selector.currentData()
        )

        self.layout_selector.blockSignals(
            True
        )

        self.layout_selector.clear()

        self.layout_selector.addItem(
            self.translate(
                "entity_graph.layout.circular",
                default="Circular",
            ),
            "circular",
        )

        layout_index = (
            self.layout_selector.findData(
                current_layout_data
            )
        )

        if layout_index >= 0:

            self.layout_selector.setCurrentIndex(
                layout_index
            )

        self.layout_selector.blockSignals(
            False
        )

        self.layout_button.setText(
            self.translate(
                "entity_graph.layout.apply",
                default="Apply Layout",
            )
        )

        self.zoom_out_button.setToolTip(
            self.translate(
                "entity_graph.zoom.out",
                default="Zoom out",
            )
        )

        self.zoom_in_button.setToolTip(
            self.translate(
                "entity_graph.zoom.in",
                default="Zoom in",
            )
        )

        self.fit_button.setText(
            self.translate(
                "entity_graph.zoom.fit",
                default="Fit",
            )
        )

        self.fit_button.setToolTip(
            self.translate(
                "entity_graph.zoom.fit_tooltip",
                default="Fit complete graph into the viewport",
            )
        )

        self.center_selected_button.setText(
            self.translate(
                "entity_graph.selection.center",
                default="Center selected",
            )
        )

        self.clear_selection_button.setText(
            self.translate(
                "entity_graph.selection.clear",
                default="Clear selection",
            )
        )

        self._update_statistics()
        self._update_graph_status()
        self._refresh_selection_details()

            # ==========================================================
    # Data
    # ==========================================================

    def set_graph_data(
        self,
        graph_data: dict[str, Any] | None,
    ) -> None:
        """
        Display graph data prepared by EntityGraphService.
        """

        self._graph_data = (
            dict(graph_data)
            if graph_data
            else {
                "nodes": [],
                "edges": [],
                "statistics": {},
            }
        )

        self.scene.set_graph_data(
            self._graph_data
        )

        self._selected_node = None
        self._selected_edge = None

        self._reset_search()

        self._update_statistics()

        self._show_empty_details()

        self._update_graph_status()

        if self.scene.node_count() == 0:

            self.graph_view.reset_zoom()

            return

        QTimer.singleShot(
            0,
            self.graph_view.fit_graph,
        )

    def clear_graph(
        self,
    ) -> None:
        """
        Clear displayed graph.
        """

        self.set_graph_data(
            None
        )

    # ==========================================================
    # Statistics
    # ==========================================================

    def _update_statistics(
        self,
    ) -> None:
        """
        Refresh graph statistics.
        """

        statistics = self._graph_data.get(
            "statistics",
            {},
        )

        nodes = self._safe_int(
            statistics.get(
                "nodes",
                self.scene.node_count(),
            )
        )

        edges = self._safe_int(
            statistics.get(
                "edges",
                self.scene.edge_count(),
            )
        )

        connected = self._safe_int(
            statistics.get(
                "connected_nodes",
                0,
            )
        )

        isolated = self._safe_int(
            statistics.get(
                "isolated_nodes",
                0,
            )
        )

        density = self._safe_float(
            statistics.get(
                "density",
                0.0,
            )
        )

        self.node_count_label.setText(
            self.translate(
                "entity_graph.statistics.nodes",
                default="Nodes: {count}",
                count=nodes,
            )
        )

        self.edge_count_label.setText(
            self.translate(
                "entity_graph.statistics.edges",
                default="Edges: {count}",
                count=edges,
            )
        )

        self.connected_count_label.setText(
            self.translate(
                "entity_graph.statistics.connected",
                default="Connected: {count}",
                count=connected,
            )
        )

        self.isolated_count_label.setText(
            self.translate(
                "entity_graph.statistics.isolated",
                default="Isolated: {count}",
                count=isolated,
            )
        )

        self.density_label.setText(
            self.translate(
                "entity_graph.statistics.density",
                default="Density: {value:.4f}",
                value=density,
            )
        )

    def _update_graph_status(
        self,
    ) -> None:
        """
        Update graph status label.
        """

        node_count = (
            self.scene.node_count()
        )

        if node_count == 0:

            self.status_label.setText(
                self.translate(
                    "entity_graph.status.empty",
                    default="No graph loaded",
                )
            )

            return

        self.status_label.setText(
            self.translate(
                "entity_graph.status.loaded",
                default="Displaying {count} entities",
                count=node_count,
            )
        )

    # ==========================================================
    # Layout
    # ==========================================================

    def _apply_selected_layout(
        self,
    ) -> None:
        """
        Apply selected graph layout.
        """

        layout_name = (
            self.layout_selector.currentData()
        )

        if layout_name == "circular":

            self.scene.apply_circular_layout()

        self.graph_view.fit_graph()

    # ==========================================================
    # Search
    # ==========================================================

    def _search_nodes(
        self,
    ) -> None:
        """
        Search graph nodes.
        """

        query = (
            self.search_input.text()
            .strip()
            .lower()
        )

        self._reset_search(
            keep_text=True
        )

        if not query:

            self._update_graph_status()

            return

        for node_item in self.scene.node_items():

            searchable_text = (
                f"{node_item.label} "
                f"{node_item.entity_type}"
            ).lower()

            if query in searchable_text:

                self._search_results.append(
                    node_item
                )

        if not self._search_results:

            self.status_label.setText(
                self.translate(
                    "entity_graph.search.no_matches",
                    default='No matches for "{query}"',
                    query=query,
                )
            )

            self.next_result_button.setEnabled(
                False
            )

            return

        self.status_label.setText(
            self.translate(
                "entity_graph.search.matches",
                default='{count} matches for "{query}"',
                count=len(
                    self._search_results
                ),
                query=query,
            )
        )

        self.next_result_button.setEnabled(
            len(
                self._search_results
            ) > 1
        )

        self._select_next_search_result()

    def _select_next_search_result(
        self,
    ) -> None:
        """
        Select next search result.
        """

        if not self._search_results:

            return

        self._search_result_index = (
            self._search_result_index + 1
        ) % len(
            self._search_results
        )

        node_item = (
            self._search_results[
                self._search_result_index
            ]
        )

        self.scene.clearSelection()

        node_item.setSelected(
            True
        )

        self.graph_view.center_on_item(
            node_item
        )

        self.status_label.setText(
            self.translate(
                "entity_graph.search.current",
                default="Match {current}/{total}: {label}",
                current=self._search_result_index + 1,
                total=len(
                    self._search_results
                ),
                label=node_item.label,
            )
        )

    def _handle_search_text_changed(
        self,
        text: str,
    ) -> None:
        """
        Reset search cache.
        """

        del text

        self._search_results.clear()

        self._search_result_index = -1

        self.next_result_button.setEnabled(
            False
        )

    def _reset_search(
        self,
        keep_text: bool = False,
    ) -> None:
        """
        Reset search state.
        """

        self._search_results.clear()

        self._search_result_index = -1

        self.next_result_button.setEnabled(
            False
        )

        if not keep_text:

            self.search_input.clear()

                # ==========================================================
    # Selection details
    # ==========================================================

    def _refresh_selection_details(
        self,
    ) -> None:
        """
        Refresh currently displayed selection.
        """

        if self._selected_node is not None:

            self._show_node_details(
                self._selected_node
            )

            return

        if self._selected_edge is not None:

            self._show_edge_details(
                self._selected_edge
            )

            return

        self._show_empty_details()

    def _show_node_details(
        self,
        node_item: GraphNodeItem,
    ) -> None:
        """
        Display selected node details.
        """

        self._selected_node = node_item
        self._selected_edge = None

        node_data = node_item.data(
            0
        )

        if not isinstance(
            node_data,
            dict,
        ):
            node_data = {}

        entity_type = (
            node_item.entity_type
            .replace(
                "_",
                " ",
            )
            .title()
        )

        isolated = bool(
            node_data.get(
                "is_isolated",
                node_item.degree == 0,
            )
        )

        self.details_title.setText(
            node_item.label
        )

        self.details_type_label.setText(
            self.translate(
                "entity_graph.details.entity",
                default="Entity · {type}",
                type=entity_type,
            )
        )

        status = (
            self.translate(
                "entity_graph.details.status_isolated",
                default="Isolated",
            )
            if isolated
            else self.translate(
                "entity_graph.details.status_connected",
                default="Connected",
            )
        )

        self.details_body.setText(
            "\n".join(
                [
                    self.translate(
                        "entity_graph.details.id",
                        default="ID: {value}",
                        value=node_item.entity_id,
                    ),
                    "",
                    self.translate(
                        "entity_graph.details.type",
                        default="Type: {value}",
                        value=entity_type,
                    ),
                    self.translate(
                        "entity_graph.details.connections",
                        default="Connections: {count}",
                        count=node_item.degree,
                    ),
                    self.translate(
                        "entity_graph.details.status",
                        default="Status: {value}",
                        value=status,
                    ),
                ]
            )
        )

        self.center_selected_button.setEnabled(
            True
        )

        self.clear_selection_button.setEnabled(
            True
        )

    def _show_edge_details(
        self,
        edge_item: GraphEdgeItem,
    ) -> None:
        """
        Display selected relationship details.
        """

        self._selected_node = None
        self._selected_edge = edge_item

        edge_data = edge_item.data(
            0
        )

        if not isinstance(
            edge_data,
            dict,
        ):
            edge_data = {}

        relationship_type = (
            edge_item.relationship_type
            .replace(
                "_",
                " ",
            )
            .title()
        )

        confidence = self._safe_float(
            edge_item.confidence
        )

        edge_id = str(
            edge_data.get(
                "id",
                self.translate(
                    "entity_graph.unknown",
                    default="Unknown",
                ),
            )
        )

        self.details_title.setText(
            relationship_type
        )

        self.details_type_label.setText(
            self.translate(
                "entity_graph.details.relationship",
                default="Relationship",
            )
        )

        self.details_body.setText(
            "\n".join(
                [
                    self.translate(
                        "entity_graph.details.id",
                        default="ID: {value}",
                        value=edge_id,
                    ),
                    "",
                    self.translate(
                        "entity_graph.details.source",
                        default="Source: {value}",
                        value=edge_item.source.label,
                    ),
                    self.translate(
                        "entity_graph.details.target",
                        default="Target: {value}",
                        value=edge_item.target.label,
                    ),
                    self.translate(
                        "entity_graph.details.type",
                        default="Type: {value}",
                        value=relationship_type,
                    ),
                    self.translate(
                        "entity_graph.details.confidence",
                        default="Confidence: {value:.2f}",
                        value=confidence,
                    ),
                ]
            )
        )

        self.center_selected_button.setEnabled(
            True
        )

        self.clear_selection_button.setEnabled(
            True
        )

    def _show_empty_details(
        self,
    ) -> None:
        """
        Display empty state.
        """

        self._selected_node = None
        self._selected_edge = None

        self.details_title.setText(
            self.translate(
                "entity_graph.details.selection",
                default="Selection",
            )
        )

        self.details_type_label.setText(
            self.translate(
                "entity_graph.details.none",
                default="Nothing selected",
            )
        )

        self.details_body.setText(
            self.translate(
                "entity_graph.details.help",
                default=(
                    "Select an entity or relationship "
                    "inside the graph to inspect it.\n\n"
                    "Mouse wheel: zoom\n"
                    "Middle mouse button: move canvas\n"
                    "Left mouse button: select or drag nodes\n"
                    "0: fit graph\n"
                    "Esc: clear selection"
                ),
            )
        )

        self.center_selected_button.setEnabled(
            False
        )

        self.clear_selection_button.setEnabled(
            False
        )

    # ==========================================================
    # Zoom
    # ==========================================================

    def _update_zoom_label(
        self,
        zoom: float,
    ) -> None:
        """
        Display current zoom.
        """

        percentage = round(
            zoom * 100
        )

        self.zoom_label.setText(
            f"{percentage}%"
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:

        try:
            return int(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> float:

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

            # ==========================================================
    # Styling
    # ==========================================================

    def _apply_styles(
        self,
    ) -> None:
        """
        Apply temporary local styles.

        These styles can later be moved into the global
        application theme during the interface redesign.
        """

        self.setStyleSheet(
            """
            QWidget {
                font-family: "Segoe UI";
            }

            QFrame#graphToolbar {
                background-color: #1c2430;
                border-bottom: 1px solid #303b49;
            }

            QLabel#graphTitle {
                color: #f3f6fa;
                font-size: 16px;
                font-weight: 600;
            }

            QLineEdit#graphSearchInput {
                min-height: 30px;
                padding: 0 10px;
                color: #eef3f8;
                background-color: #121821;
                border: 1px solid #394656;
                border-radius: 6px;
                selection-background-color: #347fc4;
            }

            QLineEdit#graphSearchInput:focus {
                border: 1px solid #4da3ff;
            }

            QPushButton#graphToolbarButton,
            QPushButton#graphSecondaryButton {
                min-height: 30px;
                padding: 0 12px;
                color: #dbe4ed;
                background-color: #27313e;
                border: 1px solid #3b4858;
                border-radius: 6px;
            }

            QPushButton#graphToolbarButton:hover,
            QPushButton#graphSecondaryButton:hover {
                background-color: #313e4d;
                border-color: #536579;
            }

            QPushButton#graphToolbarButton:pressed,
            QPushButton#graphSecondaryButton:pressed {
                background-color: #202936;
            }

            QPushButton#graphToolbarButton:disabled,
            QPushButton#graphSecondaryButton:disabled {
                color: #697687;
                background-color: #202833;
                border-color: #303a46;
            }

            QPushButton#graphZoomButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                padding: 0;
                color: #eef3f8;
                background-color: #27313e;
                border: 1px solid #3b4858;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
            }

            QPushButton#graphZoomButton:hover {
                background-color: #313e4d;
            }

            QLabel#graphZoomLabel {
                color: #aebccc;
                font-size: 12px;
            }

            QComboBox#graphLayoutSelector {
                min-height: 30px;
                padding: 0 8px;
                color: #e5ebf1;
                background-color: #27313e;
                border: 1px solid #3b4858;
                border-radius: 6px;
            }

            QComboBox#graphLayoutSelector::drop-down {
                border: none;
                width: 24px;
            }

            QComboBox#graphLayoutSelector QAbstractItemView {
                color: #e5ebf1;
                background-color: #27313e;
                border: 1px solid #465466;
                selection-background-color: #36475a;
            }

            QFrame#graphStatisticsBar {
                background-color: #181f29;
                border-bottom: 1px solid #2c3643;
            }

            QLabel#graphStatisticLabel {
                color: #aebccc;
                font-size: 12px;
            }

            QLabel#graphStatusLabel {
                color: #7f91a5;
                font-size: 12px;
            }

            QFrame#graphContainer {
                background-color: #151b24;
            }

            QFrame#graphDetailsPanel {
                background-color: #1c2430;
                border-left: 1px solid #303b49;
            }

            QLabel#graphDetailsTitle {
                color: #f1f5f9;
                font-size: 17px;
                font-weight: 600;
            }

            QLabel#graphDetailsType {
                color: #4da3ff;
                font-size: 12px;
                font-weight: 600;
            }

            QLabel#graphDetailsBody {
                color: #b8c4d1;
                font-size: 13px;
            }

            QPushButton#graphPrimaryButton {
                min-height: 34px;
                padding: 0 12px;
                color: white;
                background-color: #347fc4;
                border: 1px solid #4795dc;
                border-radius: 6px;
                font-weight: 600;
            }

            QPushButton#graphPrimaryButton:hover {
                background-color: #3d8bd2;
            }

            QPushButton#graphPrimaryButton:disabled {
                color: #718093;
                background-color: #27313d;
                border-color: #34404d;
            }

            QSplitter#graphSplitter::handle {
                width: 1px;
                background-color: #303b49;
            }
            """
        )