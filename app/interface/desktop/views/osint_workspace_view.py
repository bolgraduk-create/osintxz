"""
OSINT workspace view.

Responsible for:

- displaying the OSINT investigation form
- collecting structured form data
- displaying investigation actions
- providing investigation, results and history tabs
- emitting workspace actions
- displaying workspace state
- displaying loading and execution status
- reacting to application language changes

Does NOT:

- execute OSINT connectors
- access database
- contain OSINT business logic
- create application models
- call AI
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import (
    QDate,
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.interface.desktop.widgets import (
    Card,
    Toolbar,
)

from app.interface.desktop.localization import (
    TranslatableMixin,
)

from app.localization import (
    TranslationManager,
    get_translation_manager,
)


class OsintWorkspaceView(
    TranslatableMixin,
    QWidget,
):
    """
    Main OSINT workspace UI container.

    The view owns only presentation state.

    Structured dictionaries produced by this view are passed
    to OsintController by OsintWorkspacePage.
    """

    preview_requested = Signal()

    connectors_requested = Signal()

    run_requested = Signal()

    refresh_requested = Signal()

    clear_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        translation_manager: TranslationManager | None = None,
    ) -> None:

        super().__init__(
            parent
        )

        self._workspace_state: dict[
            str,
            Any,
        ] = {}

        self._loading = False

        self._target_count = 0
        self._connector_count = 0
        self._result_count = 0
        self._lead_count = 0

        self._status_mode = "ready"
        self._status_message: str | None = None
        self._status_connector_count = 0

        self._translation_bindings: list[
            tuple[QWidget, str, str, str]
        ] = []

        self._setup_ui()
        self._collect_translation_bindings()

        active_translation_manager = (
            translation_manager
            if translation_manager is not None
            else get_translation_manager()
        )

        self.initialize_translations(
            active_translation_manager
        )

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create the OSINT workspace.
        """

        self.setObjectName(
            "OsintWorkspaceView"
        )

        self.main_layout = QVBoxLayout(
            self
        )

        self.main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.main_layout.setSpacing(
            16
        )

        self._create_toolbar()
        self._create_tabs()

    # ==========================================================
    # Toolbar
    # ==========================================================

    def _create_toolbar(
        self,
    ) -> None:
        """
        Create OSINT workspace toolbar.
        """

        self.toolbar = Toolbar(
            parent=self
        )

        self.toolbar.setObjectName(
            "OsintWorkspaceToolbar"
        )

        self.toolbar.set_variant(
            "default"
        )

        self.preview_button = QPushButton(
            "Preview Targets",
            self.toolbar,
        )

        self.preview_button.setObjectName(
            "OsintPreviewTargetsButton"
        )

        self.preview_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.preview_button.setToolTip(
            "Build OSINT targets without running connectors"
        )

        self.preview_button.clicked.connect(
            self.preview_requested.emit
        )

        self.connectors_button = QPushButton(
            "Find Connectors",
            self.toolbar,
        )

        self.connectors_button.setObjectName(
            "OsintFindConnectorsButton"
        )

        self.connectors_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.connectors_button.setToolTip(
            "Find compatible connectors for the current targets"
        )

        self.connectors_button.clicked.connect(
            self.connectors_requested.emit
        )

        self.run_button = QPushButton(
            "Run Investigation",
            self.toolbar,
        )

        self.run_button.setObjectName(
            "OsintRunInvestigationButton"
        )

        self.run_button.setProperty(
            "variant",
            "primary",
        )

        self.run_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.run_button.setToolTip(
            "Run the OSINT investigation"
        )

        self.run_button.clicked.connect(
            self.run_requested.emit
        )

        self.refresh_button = QPushButton(
            "Refresh",
            self.toolbar,
        )

        self.refresh_button.setObjectName(
            "OsintRefreshButton"
        )

        self.refresh_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.refresh_button.setToolTip(
            "Reload OSINT workspace state"
        )

        self.refresh_button.clicked.connect(
            self.refresh_requested.emit
        )

        self.clear_button = QPushButton(
            "Clear",
            self.toolbar,
        )

        self.clear_button.setObjectName(
            "OsintClearButton"
        )

        self.clear_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.clear_button.setToolTip(
            "Clear the current investigation form and results"
        )

        self.clear_button.clicked.connect(
            self.clear_requested.emit
        )

        self.workspace_status_label = QLabel(
            "OSINT workspace ready",
            self.toolbar,
        )

        self.workspace_status_label.setObjectName(
            "OsintWorkspaceStatusLabel"
        )

        self.workspace_status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.toolbar.add_left_widget(
            self.preview_button
        )

        self.toolbar.add_left_widget(
            self.connectors_button
        )

        self.toolbar.add_left_widget(
            self.run_button
        )

        self.toolbar.add_left_widget(
            self.refresh_button
        )

        self.toolbar.add_left_widget(
            self.clear_button
        )

        self.toolbar.add_right_widget(
            self.workspace_status_label
        )

        self.main_layout.addWidget(
            self.toolbar
        )

    # ==========================================================
    # Tabs
    # ==========================================================

    def _create_tabs(
        self,
    ) -> None:
        """
        Create OSINT workspace tabs.
        """

        self.tabs = QTabWidget(
            self
        )

        self.tabs.setObjectName(
            "OsintWorkspaceTabs"
        )

        self.tabs.setDocumentMode(
            True
        )

        self.tabs.setMovable(
            False
        )

        self.tabs.setTabsClosable(
            False
        )

        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._create_investigation_tab()
        self._create_results_tab()
        self._create_history_tab()

        self.main_layout.addWidget(
            self.tabs,
            1,
        )

    # ==========================================================
    # Localization
    # ==========================================================

    def _collect_translation_bindings(
        self,
    ) -> None:
        """
        Collect references to static translatable widget text.

        The original widget construction remains unchanged. Bindings
        are captured once, before the first translation is applied, so
        later language switches do not depend on the currently visible
        text.
        """

        text_keys = {
            "Preview Targets": "osint_workspace.action.preview_targets",
            "Find Connectors": "osint_workspace.action.find_connectors",
            "Run Investigation": "osint_workspace.action.run_investigation",
            "Refresh": "osint_workspace.action.refresh",
            "Clear": "osint_workspace.action.clear",
            "OSINT workspace ready": "osint_workspace.status.ready",
            "OSINT Investigation": "osint_workspace.investigation.title",
            (
                "Enter all currently known information. "
                "The application will convert it into independent "
                "targets and select compatible OSINT connectors."
            ): "osint_workspace.investigation.subtitle",
            (
                "You do not need to complete every field. "
                "A single username, email address, phone number, "
                "domain, IP address or person name is enough."
            ): "osint_workspace.investigation.help",
            "Investigation Context": "osint_workspace.context.title",
            (
                "General information used to identify and describe "
                "the current OSINT operation."
            ): "osint_workspace.context.subtitle",
            "Case ID": "osint_workspace.field.case_id",
            "Title": "osint_workspace.field.title",
            "Description": "osint_workspace.field.description",
            "Person Identity": "osint_workspace.person.title",
            (
                "Known identity information. Name fields are "
                "combined into a single person target."
            ): "osint_workspace.person.subtitle",
            "First name": "osint_workspace.field.first_name",
            "Middle name": "osint_workspace.field.middle_name",
            "Last name": "osint_workspace.field.last_name",
            "Birth date is known": "osint_workspace.field.birth_date_known",
            "Accounts and Contacts": "osint_workspace.contacts.title",
            (
                "Enter one value per line. Duplicates will be "
                "removed by the target builder."
            ): "osint_workspace.contacts.subtitle",
            "Usernames": "osint_workspace.field.usernames",
            "Emails": "osint_workspace.field.emails",
            "Phones": "osint_workspace.field.phones",
            "Location and Organizations": "osint_workspace.location.title",
            (
                "Location fields are combined into one location "
                "target. Organizations remain separate targets."
            ): "osint_workspace.location.subtitle",
            "Country": "osint_workspace.field.country",
            "Region": "osint_workspace.field.region",
            "City": "osint_workspace.field.city",
            "Postal code": "osint_workspace.field.postal_code",
            "Address": "osint_workspace.field.address",
            "Organizations": "osint_workspace.field.organizations",
            "Network and Web Targets": "osint_workspace.network.title",
            (
                "Domains, URLs and IP addresses are converted "
                "into independent targets."
            ): "osint_workspace.network.subtitle",
            "Domains": "osint_workspace.field.domains",
            "URLs": "osint_workspace.field.urls",
            "IP addresses": "osint_workspace.field.ip_addresses",
            "Hashes and Local Artifacts": "osint_workspace.artifacts.title",
            (
                "Add known hashes or local files and images "
                "that should be treated as OSINT targets."
            ): "osint_workspace.artifacts.subtitle",
            "Hashes": "osint_workspace.field.hashes",
            "Files": "osint_workspace.field.files",
            "Images": "osint_workspace.field.images",
            "Add Files": "osint_workspace.action.add_files",
            "Add Images": "osint_workspace.action.add_images",
            "Execution Settings": "osint_workspace.execution.title",
            (
                "Optional settings passed to the OSINT execution "
                "pipeline."
            ): "osint_workspace.execution.subtitle",
            "Use cached results when available": (
                "osint_workspace.execution.use_cache"
            ),
            "Save raw connector output": (
                "osint_workspace.execution.save_raw_output"
            ),
            "Include connector metadata": (
                "osint_workspace.execution.include_metadata"
            ),
            "Include related findings": (
                "osint_workspace.execution.include_related"
            ),
            "Selected connectors": (
                "osint_workspace.field.selected_connectors"
            ),
            "Timeout": "osint_workspace.field.timeout",
            "Keywords and Notes": "osint_workspace.notes.title",
            (
                "Additional context is attached to generated "
                "targets but does not create independent targets."
            ): "osint_workspace.notes.subtitle",
            "Keywords": "osint_workspace.field.keywords",
            "Notes": "osint_workspace.field.notes",
            "Find Compatible Connectors": (
                "osint_workspace.action.find_compatible_connectors"
            ),
            "Investigation Results": "osint_workspace.results.title",
            (
                "Targets, compatible connectors and connector "
                "execution results will appear here."
            ): "osint_workspace.results.subtitle",
            "Targets: 0": "osint_workspace.summary.targets_zero",
            "Connectors: 0": "osint_workspace.summary.connectors_zero",
            "Results: 0": "osint_workspace.summary.results_zero",
            "No OSINT results": "osint_workspace.results.empty_title",
            (
                "Preview targets or run an investigation "
                "to populate this workspace."
            ): "osint_workspace.results.empty_subtitle",
            (
                "The next implementation step will display:\n\n"
                "• Generated targets\n"
                "• Compatible connectors\n"
                "• Connector execution status\n"
                "• Findings\n"
                "• Errors and diagnostic output\n"
                "• Raw result metadata"
            ): "osint_workspace.results.placeholder",
            "Investigation History": "osint_workspace.history.title",
            (
                "Saved and previously executed investigations "
                "will be displayed here in a later stage."
            ): "osint_workspace.history.subtitle",
            (
                "History storage is not connected yet.\n\n"
                "Current OSINT execution remains stateless."
            ): "osint_workspace.history.placeholder",
        }

        placeholder_keys = {
            "Optional investigation or case identifier": (
                "osint_workspace.placeholder.case_id"
            ),
            "Example: Investigation of online identity": (
                "osint_workspace.placeholder.title"
            ),
            "Describe the purpose and known context...": (
                "osint_workspace.placeholder.description"
            ),
            "First name": "osint_workspace.placeholder.first_name",
            "Middle name": "osint_workspace.placeholder.middle_name",
            "Last name": "osint_workspace.placeholder.last_name",
            "usernames, one per line": (
                "osint_workspace.placeholder.usernames"
            ),
            "email addresses, one per line": (
                "osint_workspace.placeholder.emails"
            ),
            "phone numbers, one per line": (
                "osint_workspace.placeholder.phones"
            ),
            "Country": "osint_workspace.placeholder.country",
            "Region or state": "osint_workspace.placeholder.region",
            "City": "osint_workspace.placeholder.city",
            "Postal code": "osint_workspace.placeholder.postal_code",
            "Street address": "osint_workspace.placeholder.address",
            "organizations, one per line": (
                "osint_workspace.placeholder.organizations"
            ),
            "example.com": "osint_workspace.placeholder.domains",
            "https://example.com/profile": (
                "osint_workspace.placeholder.urls"
            ),
            "IP addresses, one per line": (
                "osint_workspace.placeholder.ip_addresses"
            ),
            "MD5, SHA-1 or SHA-256 hashes": (
                "osint_workspace.placeholder.hashes"
            ),
            "local file paths": "osint_workspace.placeholder.file_paths",
            "local image paths": "osint_workspace.placeholder.image_paths",
            (
                "Optional connector names. "
                "Leave empty to run all compatible connectors."
            ): "osint_workspace.placeholder.selected_connectors",
            "keywords, one per line": (
                "osint_workspace.placeholder.keywords"
            ),
            "Investigation notes, assumptions and context...": (
                "osint_workspace.placeholder.notes"
            ),
        }

        tooltip_keys = {
            "Build OSINT targets without running connectors": (
                "osint_workspace.action.preview_targets_tooltip"
            ),
            "Find compatible connectors for the current targets": (
                "osint_workspace.action.find_connectors_tooltip"
            ),
            "Run the OSINT investigation": (
                "osint_workspace.action.run_investigation_tooltip"
            ),
            "Reload OSINT workspace state": (
                "osint_workspace.action.refresh_tooltip"
            ),
            "Clear the current investigation form and results": (
                "osint_workspace.action.clear_tooltip"
            ),
        }

        for widget in self.findChildren(
            QWidget
        ):

            if isinstance(
                widget,
                (
                    QLabel,
                    QPushButton,
                    QCheckBox,
                ),
            ):

                default_text = widget.text()
                key = text_keys.get(
                    default_text
                )

                if key:

                    self._translation_bindings.append(
                        (
                            widget,
                            "text",
                            key,
                            default_text,
                        )
                    )

            if isinstance(
                widget,
                (
                    QLineEdit,
                    QPlainTextEdit,
                ),
            ):

                default_placeholder = (
                    widget.placeholderText()
                )

                key = placeholder_keys.get(
                    default_placeholder
                )

                if key:

                    self._translation_bindings.append(
                        (
                            widget,
                            "placeholder",
                            key,
                            default_placeholder,
                        )
                    )

            default_tooltip = widget.toolTip()
            key = tooltip_keys.get(
                default_tooltip
            )

            if key:

                self._translation_bindings.append(
                    (
                        widget,
                        "tooltip",
                        key,
                        default_tooltip,
                    )
                )

        self._translation_bindings.append(
            (
                self.timeout_input,
                "suffix",
                "osint_workspace.execution.seconds_suffix",
                " seconds",
            )
        )

    def retranslate_ui(
        self,
    ) -> None:
        """
        Apply the active application language.
        """

        for (
            widget,
            binding_type,
            key,
            default,
        ) in self._translation_bindings:

            translated_text = self.translate(
                key,
                default=default,
            )

            if binding_type == "text":

                widget.setText(
                    translated_text
                )

            elif binding_type == "placeholder":

                widget.setPlaceholderText(
                    translated_text
                )

            elif binding_type == "tooltip":

                widget.setToolTip(
                    translated_text
                )

            elif binding_type == "suffix":

                widget.setSuffix(
                    translated_text
                )

        investigation_index = self.tabs.indexOf(
            self.investigation_scroll
        )

        if investigation_index >= 0:

            self.tabs.setTabText(
                investigation_index,
                self.translate(
                    "osint_workspace.tab.investigation",
                    default="Investigation",
                ),
            )

        results_index = self.tabs.indexOf(
            self.results_scroll
        )

        if results_index >= 0:

            self.tabs.setTabText(
                results_index,
                self.translate(
                    "osint_workspace.tab.results",
                    default="Results",
                ),
            )

        history_index = self.tabs.indexOf(
            self.history_container
        )

        if history_index >= 0:

            self.tabs.setTabText(
                history_index,
                self.translate(
                    "osint_workspace.tab.history",
                    default="History",
                ),
            )

        self._update_summary_labels()
        self._update_action_labels()
        self._update_status_label()

    def _update_action_labels(
        self,
    ) -> None:
        """
        Update controls whose text depends on loading state.
        """

        run_text = self.translate(
            (
                "osint_workspace.status.running_button"
                if self._loading
                else "osint_workspace.action.run_investigation"
            ),
            default=(
                "Running..."
                if self._loading
                else "Run Investigation"
            ),
        )

        self.run_button.setText(
            run_text
        )

        self.form_run_button.setText(
            run_text
        )

    def _update_summary_labels(
        self,
    ) -> None:
        """
        Update translated production result counters.
        """

        self.target_count_label.setText(
            self.translate(
                "osint_workspace.summary.targets",
                default="Targets: {count}",
                count=self._target_count,
            )
        )

        self.connector_count_label.setText(
            self.translate(
                "osint_workspace.summary.connectors",
                default="Connectors: {count}",
                count=self._connector_count,
            )
        )

        self.result_count_label.setText(
            self.translate(
                "osint_workspace.summary.findings",
                default="Findings: {count}",
                count=self._result_count,
            )
        )

        self.lead_count_label.setText(
            self.translate(
                "osint_workspace.summary.leads",
                default="Leads: {count}",
                count=self._lead_count,
            )
        )

    def _update_status_label(
        self,
    ) -> None:
        """
        Update the translated workspace status.
        """

        if self._status_mode == "custom":

            status_text = (
                self._status_message
                or self.translate(
                    "osint_workspace.status.ready",
                    default="OSINT workspace ready",
                )
            )

        elif self._status_mode == "error":

            if self._status_message:

                status_text = self.translate(
                    "osint_workspace.status.error",
                    default="Error: {message}",
                    message=self._status_message,
                )

            else:

                status_text = self.translate(
                    "osint_workspace.status.failed",
                    default="OSINT operation failed",
                )

        elif self._status_mode == "loading":

            status_text = (
                self._status_message
                or self.translate(
                    "osint_workspace.status.running",
                    default="Running OSINT investigation...",
                )
            )

        elif self._status_mode == "loaded":

            status_text = self.translate(
                "osint_workspace.status.loaded",
                default=(
                    "OSINT workspace loaded · "
                    "{count} connectors registered"
                ),
                count=self._status_connector_count,
            )

        elif self._status_mode == "cleared":

            status_text = self.translate(
                "osint_workspace.status.cleared",
                default="OSINT workspace cleared",
            )

        else:

            status_text = self.translate(
                "osint_workspace.status.ready",
                default="OSINT workspace ready",
            )

        self.workspace_status_label.setText(
            status_text
        )

    # ==========================================================
    # Investigation tab
    # ==========================================================

    def _create_investigation_tab(
        self,
    ) -> None:
        """
        Create the structured investigation form.
        """

        self.investigation_scroll = QScrollArea(
            self.tabs
        )

        self.investigation_scroll.setObjectName(
            "OsintInvestigationScroll"
        )

        self.investigation_scroll.setWidgetResizable(
            True
        )

        self.investigation_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.investigation_container = QWidget()

        self.investigation_container.setObjectName(
            "OsintInvestigationContainer"
        )

        self.investigation_layout = QVBoxLayout(
            self.investigation_container
        )

        self.investigation_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.investigation_layout.setSpacing(
            16
        )

        self._create_investigation_header()
        self._create_context_card()
        self._create_person_card()
        self._create_contacts_card()
        self._create_location_card()
        self._create_network_card()
        self._create_artifacts_card()
        self._create_execution_card()
        self._create_notes_card()
        self._create_form_actions()

        self.investigation_layout.addStretch(
            1
        )

        self.investigation_scroll.setWidget(
            self.investigation_container
        )

        self.tabs.addTab(
            self.investigation_scroll,
            "Investigation",
        )

    def _create_investigation_header(
        self,
    ) -> None:
        """
        Create investigation introduction card.
        """

        self.investigation_header_card = Card(
            title="OSINT Investigation",
            subtitle=(
                "Enter all currently known information. "
                "The application will convert it into independent "
                "targets and select compatible OSINT connectors."
            ),
            parent=self.investigation_container,
        )

        self.investigation_header_card.setObjectName(
            "OsintInvestigationHeaderCard"
        )

        self.investigation_header_card.set_variant(
            "elevated"
        )

        self.investigation_help_label = QLabel(
            (
                "You do not need to complete every field. "
                "A single username, email address, phone number, "
                "domain, IP address or person name is enough."
            ),
            self.investigation_header_card,
        )

        self.investigation_help_label.setObjectName(
            "OsintInvestigationHelpLabel"
        )

        self.investigation_help_label.setWordWrap(
            True
        )

        self.investigation_header_card.add_widget(
            self.investigation_help_label
        )

        self.investigation_layout.addWidget(
            self.investigation_header_card
        )

    # ==========================================================
    # Context
    # ==========================================================

    def _create_context_card(
        self,
    ) -> None:
        """
        Create general investigation context fields.
        """

        self.context_card = Card(
            title="Investigation Context",
            subtitle=(
                "General information used to identify and describe "
                "the current OSINT operation."
            ),
            parent=self.investigation_container,
        )

        self.context_card.setObjectName(
            "OsintContextCard"
        )

        self.context_card.set_variant(
            "default"
        )

        context_container = QWidget(
            self.context_card
        )

        context_form = QFormLayout(
            context_container
        )

        self._configure_form_layout(
            context_form
        )

        self.case_id_input = QLineEdit(
            context_container
        )

        self.case_id_input.setObjectName(
            "OsintCaseIdInput"
        )

        self.case_id_input.setPlaceholderText(
            "Optional investigation or case identifier"
        )

        self.title_input = QLineEdit(
            context_container
        )

        self.title_input.setObjectName(
            "OsintTitleInput"
        )

        self.title_input.setPlaceholderText(
            "Example: Investigation of online identity"
        )

        self.description_input = QPlainTextEdit(
            context_container
        )

        self.description_input.setObjectName(
            "OsintDescriptionInput"
        )

        self.description_input.setPlaceholderText(
            "Describe the purpose and known context..."
        )

        self.description_input.setMinimumHeight(
            90
        )

        context_form.addRow(
            "Case ID",
            self.case_id_input,
        )

        context_form.addRow(
            "Title",
            self.title_input,
        )

        context_form.addRow(
            "Description",
            self.description_input,
        )

        self.context_card.add_widget(
            context_container
        )

        self.investigation_layout.addWidget(
            self.context_card
        )

    # ==========================================================
    # Person
    # ==========================================================

    def _create_person_card(
        self,
    ) -> None:
        """
        Create person identity fields.
        """

        self.person_card = Card(
            title="Person Identity",
            subtitle=(
                "Known identity information. Name fields are "
                "combined into a single person target."
            ),
            parent=self.investigation_container,
        )

        self.person_card.setObjectName(
            "OsintPersonCard"
        )

        self.person_card.set_variant(
            "default"
        )

        person_container = QWidget(
            self.person_card
        )

        person_layout = QGridLayout(
            person_container
        )

        person_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        person_layout.setHorizontalSpacing(
            16
        )

        person_layout.setVerticalSpacing(
            10
        )

        self.first_name_input = self._create_line_input(
            person_container,
            "First name",
        )

        self.middle_name_input = self._create_line_input(
            person_container,
            "Middle name",
        )

        self.last_name_input = self._create_line_input(
            person_container,
            "Last name",
        )

        first_name_label = QLabel(
            "First name",
            person_container,
        )

        middle_name_label = QLabel(
            "Middle name",
            person_container,
        )

        last_name_label = QLabel(
            "Last name",
            person_container,
        )

        person_layout.addWidget(
            first_name_label,
            0,
            0,
        )

        person_layout.addWidget(
            middle_name_label,
            0,
            1,
        )

        person_layout.addWidget(
            last_name_label,
            0,
            2,
        )

        person_layout.addWidget(
            self.first_name_input,
            1,
            0,
        )

        person_layout.addWidget(
            self.middle_name_input,
            1,
            1,
        )

        person_layout.addWidget(
            self.last_name_input,
            1,
            2,
        )

        self.birth_date_enabled = QCheckBox(
            "Birth date is known",
            person_container,
        )

        self.birth_date_enabled.setObjectName(
            "OsintBirthDateEnabled"
        )

        self.birth_date_input = QDateEdit(
            person_container
        )

        self.birth_date_input.setObjectName(
            "OsintBirthDateInput"
        )

        self.birth_date_input.setCalendarPopup(
            True
        )

        self.birth_date_input.setDisplayFormat(
            "yyyy-MM-dd"
        )

        self.birth_date_input.setMaximumDate(
            QDate.currentDate()
        )

        self.birth_date_input.setDate(
            QDate.currentDate()
        )

        self.birth_date_input.setEnabled(
            False
        )

        self.birth_date_enabled.toggled.connect(
            self.birth_date_input.setEnabled
        )

        person_layout.addWidget(
            self.birth_date_enabled,
            2,
            0,
        )

        person_layout.addWidget(
            self.birth_date_input,
            2,
            1,
            1,
            2,
        )

        for column in range(
            3
        ):

            person_layout.setColumnStretch(
                column,
                1,
            )

        self.person_card.add_widget(
            person_container
        )

        self.investigation_layout.addWidget(
            self.person_card
        )

    # ==========================================================
    # Contacts
    # ==========================================================

    def _create_contacts_card(
        self,
    ) -> None:
        """
        Create usernames, emails and phone fields.
        """

        self.contacts_card = Card(
            title="Accounts and Contacts",
            subtitle=(
                "Enter one value per line. Duplicates will be "
                "removed by the target builder."
            ),
            parent=self.investigation_container,
        )

        self.contacts_card.setObjectName(
            "OsintContactsCard"
        )

        self.contacts_card.set_variant(
            "default"
        )

        contacts_container = QWidget(
            self.contacts_card
        )

        contacts_layout = QGridLayout(
            contacts_container
        )

        contacts_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        contacts_layout.setHorizontalSpacing(
            16
        )

        contacts_layout.setVerticalSpacing(
            8
        )

        self.usernames_input = self._create_list_input(
            contacts_container,
            "usernames, one per line",
        )

        self.emails_input = self._create_list_input(
            contacts_container,
            "email addresses, one per line",
        )

        self.phones_input = self._create_list_input(
            contacts_container,
            "phone numbers, one per line",
        )

        contacts_layout.addWidget(
            QLabel(
                "Usernames",
                contacts_container,
            ),
            0,
            0,
        )

        contacts_layout.addWidget(
            QLabel(
                "Emails",
                contacts_container,
            ),
            0,
            1,
        )

        contacts_layout.addWidget(
            QLabel(
                "Phones",
                contacts_container,
            ),
            0,
            2,
        )

        contacts_layout.addWidget(
            self.usernames_input,
            1,
            0,
        )

        contacts_layout.addWidget(
            self.emails_input,
            1,
            1,
        )

        contacts_layout.addWidget(
            self.phones_input,
            1,
            2,
        )

        for column in range(
            3
        ):

            contacts_layout.setColumnStretch(
                column,
                1,
            )

        self.contacts_card.add_widget(
            contacts_container
        )

        self.investigation_layout.addWidget(
            self.contacts_card
        )

    # ==========================================================
    # Location
    # ==========================================================

    def _create_location_card(
        self,
    ) -> None:
        """
        Create location and organization fields.
        """

        self.location_card = Card(
            title="Location and Organizations",
            subtitle=(
                "Location fields are combined into one location "
                "target. Organizations remain separate targets."
            ),
            parent=self.investigation_container,
        )

        self.location_card.setObjectName(
            "OsintLocationCard"
        )

        self.location_card.set_variant(
            "default"
        )

        location_container = QWidget(
            self.location_card
        )

        location_layout = QGridLayout(
            location_container
        )

        location_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        location_layout.setHorizontalSpacing(
            16
        )

        location_layout.setVerticalSpacing(
            10
        )

        self.country_input = self._create_line_input(
            location_container,
            "Country",
        )

        self.region_input = self._create_line_input(
            location_container,
            "Region or state",
        )

        self.city_input = self._create_line_input(
            location_container,
            "City",
        )

        self.postal_code_input = self._create_line_input(
            location_container,
            "Postal code",
        )

        self.address_input = self._create_line_input(
            location_container,
            "Street address",
        )

        self.organizations_input = self._create_list_input(
            location_container,
            "organizations, one per line",
        )

        location_layout.addWidget(
            QLabel(
                "Country",
                location_container,
            ),
            0,
            0,
        )

        location_layout.addWidget(
            QLabel(
                "Region",
                location_container,
            ),
            0,
            1,
        )

        location_layout.addWidget(
            QLabel(
                "City",
                location_container,
            ),
            0,
            2,
        )

        location_layout.addWidget(
            self.country_input,
            1,
            0,
        )

        location_layout.addWidget(
            self.region_input,
            1,
            1,
        )

        location_layout.addWidget(
            self.city_input,
            1,
            2,
        )

        location_layout.addWidget(
            QLabel(
                "Postal code",
                location_container,
            ),
            2,
            0,
        )

        location_layout.addWidget(
            QLabel(
                "Address",
                location_container,
            ),
            2,
            1,
            1,
            2,
        )

        location_layout.addWidget(
            self.postal_code_input,
            3,
            0,
        )

        location_layout.addWidget(
            self.address_input,
            3,
            1,
            1,
            2,
        )

        location_layout.addWidget(
            QLabel(
                "Organizations",
                location_container,
            ),
            4,
            0,
            1,
            3,
        )

        location_layout.addWidget(
            self.organizations_input,
            5,
            0,
            1,
            3,
        )

        for column in range(
            3
        ):

            location_layout.setColumnStretch(
                column,
                1,
            )

        self.location_card.add_widget(
            location_container
        )

        self.investigation_layout.addWidget(
            self.location_card
        )

    # ==========================================================
    # Network targets
    # ==========================================================

    def _create_network_card(
        self,
    ) -> None:
        """
        Create domains, URLs and IP address fields.
        """

        self.network_card = Card(
            title="Network and Web Targets",
            subtitle=(
                "Domains, URLs and IP addresses are converted "
                "into independent targets."
            ),
            parent=self.investigation_container,
        )

        self.network_card.setObjectName(
            "OsintNetworkCard"
        )

        self.network_card.set_variant(
            "default"
        )

        network_container = QWidget(
            self.network_card
        )

        network_layout = QGridLayout(
            network_container
        )

        network_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        network_layout.setHorizontalSpacing(
            16
        )

        network_layout.setVerticalSpacing(
            8
        )

        self.domains_input = self._create_list_input(
            network_container,
            "example.com",
        )

        self.urls_input = self._create_list_input(
            network_container,
            "https://example.com/profile",
        )

        self.ip_addresses_input = self._create_list_input(
            network_container,
            "IP addresses, one per line",
        )

        network_layout.addWidget(
            QLabel(
                "Domains",
                network_container,
            ),
            0,
            0,
        )

        network_layout.addWidget(
            QLabel(
                "URLs",
                network_container,
            ),
            0,
            1,
        )

        network_layout.addWidget(
            QLabel(
                "IP addresses",
                network_container,
            ),
            0,
            2,
        )

        network_layout.addWidget(
            self.domains_input,
            1,
            0,
        )

        network_layout.addWidget(
            self.urls_input,
            1,
            1,
        )

        network_layout.addWidget(
            self.ip_addresses_input,
            1,
            2,
        )

        for column in range(
            3
        ):

            network_layout.setColumnStretch(
                column,
                1,
            )

        self.network_card.add_widget(
            network_container
        )

        self.investigation_layout.addWidget(
            self.network_card
        )

    # ==========================================================
    # Artifacts
    # ==========================================================

    def _create_artifacts_card(
        self,
    ) -> None:
        """
        Create hashes and local artifact fields.
        """

        self.artifacts_card = Card(
            title="Hashes and Local Artifacts",
            subtitle=(
                "Add known hashes or local files and images "
                "that should be treated as OSINT targets."
            ),
            parent=self.investigation_container,
        )

        self.artifacts_card.setObjectName(
            "OsintArtifactsCard"
        )

        self.artifacts_card.set_variant(
            "default"
        )

        artifacts_container = QWidget(
            self.artifacts_card
        )

        artifacts_layout = QGridLayout(
            artifacts_container
        )

        artifacts_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        artifacts_layout.setHorizontalSpacing(
            16
        )

        artifacts_layout.setVerticalSpacing(
            8
        )

        self.hashes_input = self._create_list_input(
            artifacts_container,
            "MD5, SHA-1 or SHA-256 hashes",
        )

        self.file_paths_input = self._create_list_input(
            artifacts_container,
            "local file paths",
        )

        self.image_paths_input = self._create_list_input(
            artifacts_container,
            "local image paths",
        )

        artifacts_layout.addWidget(
            QLabel(
                "Hashes",
                artifacts_container,
            ),
            0,
            0,
        )

        artifacts_layout.addWidget(
            QLabel(
                "Files",
                artifacts_container,
            ),
            0,
            1,
        )

        artifacts_layout.addWidget(
            QLabel(
                "Images",
                artifacts_container,
            ),
            0,
            2,
        )

        artifacts_layout.addWidget(
            self.hashes_input,
            1,
            0,
        )

        artifacts_layout.addWidget(
            self.file_paths_input,
            1,
            1,
        )

        artifacts_layout.addWidget(
            self.image_paths_input,
            1,
            2,
        )

        self.add_files_button = QPushButton(
            "Add Files",
            artifacts_container,
        )

        self.add_files_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.add_files_button.clicked.connect(
            self._select_files
        )

        self.add_images_button = QPushButton(
            "Add Images",
            artifacts_container,
        )

        self.add_images_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.add_images_button.clicked.connect(
            self._select_images
        )

        artifacts_layout.addWidget(
            self.add_files_button,
            2,
            1,
        )

        artifacts_layout.addWidget(
            self.add_images_button,
            2,
            2,
        )

        for column in range(
            3
        ):

            artifacts_layout.setColumnStretch(
                column,
                1,
            )

        self.artifacts_card.add_widget(
            artifacts_container
        )

        self.investigation_layout.addWidget(
            self.artifacts_card
        )

    # ==========================================================
    # Execution settings
    # ==========================================================

    def _create_execution_card(
        self,
    ) -> None:
        """
        Create connector execution settings.
        """

        self.execution_card = Card(
            title="Execution Settings",
            subtitle=(
                "Optional settings passed to the OSINT execution "
                "pipeline."
            ),
            parent=self.investigation_container,
        )

        self.execution_card.setObjectName(
            "OsintExecutionCard"
        )

        self.execution_card.set_variant(
            "default"
        )

        execution_container = QWidget(
            self.execution_card
        )

        execution_layout = QGridLayout(
            execution_container
        )

        execution_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        execution_layout.setHorizontalSpacing(
            20
        )

        execution_layout.setVerticalSpacing(
            10
        )

        self.selected_connectors_input = (
            self._create_list_input(
                execution_container,
                (
                    "Optional connector names. "
                    "Leave empty to run all compatible connectors."
                ),
            )
        )

        self.timeout_input = QSpinBox(
            execution_container
        )

        self.timeout_input.setObjectName(
            "OsintTimeoutInput"
        )

        self.timeout_input.setRange(
            1,
            3600,
        )

        self.timeout_input.setValue(
            300
        )

        self.timeout_input.setSuffix(
            " seconds"
        )

        self.use_cache_checkbox = QCheckBox(
            "Use cached results when available",
            execution_container,
        )

        self.use_cache_checkbox.setObjectName(
            "OsintUseCacheCheckbox"
        )

        self.use_cache_checkbox.setChecked(
            True
        )

        self.save_raw_output_checkbox = QCheckBox(
            "Save raw connector output",
            execution_container,
        )

        self.save_raw_output_checkbox.setObjectName(
            "OsintSaveRawOutputCheckbox"
        )

        self.include_metadata_checkbox = QCheckBox(
            "Include connector metadata",
            execution_container,
        )

        self.include_metadata_checkbox.setObjectName(
            "OsintIncludeMetadataCheckbox"
        )

        self.include_metadata_checkbox.setChecked(
            True
        )

        self.include_related_checkbox = QCheckBox(
            "Include related findings",
            execution_container,
        )

        self.include_related_checkbox.setObjectName(
            "OsintIncludeRelatedCheckbox"
        )

        self.include_related_checkbox.setChecked(
            True
        )

        execution_layout.addWidget(
            QLabel(
                "Selected connectors",
                execution_container,
            ),
            0,
            0,
        )

        execution_layout.addWidget(
            self.selected_connectors_input,
            1,
            0,
            5,
            1,
        )

        execution_layout.addWidget(
            QLabel(
                "Timeout",
                execution_container,
            ),
            0,
            1,
        )

        execution_layout.addWidget(
            self.timeout_input,
            1,
            1,
        )

        execution_layout.addWidget(
            self.use_cache_checkbox,
            2,
            1,
        )

        execution_layout.addWidget(
            self.save_raw_output_checkbox,
            3,
            1,
        )

        execution_layout.addWidget(
            self.include_metadata_checkbox,
            4,
            1,
        )

        execution_layout.addWidget(
            self.include_related_checkbox,
            5,
            1,
        )

        execution_layout.setColumnStretch(
            0,
            2,
        )

        execution_layout.setColumnStretch(
            1,
            1,
        )

        self.execution_card.add_widget(
            execution_container
        )

        self.investigation_layout.addWidget(
            self.execution_card
        )

    # ==========================================================
    # Keywords and notes
    # ==========================================================

    def _create_notes_card(
        self,
    ) -> None:
        """
        Create keywords and notes fields.
        """

        self.notes_card = Card(
            title="Keywords and Notes",
            subtitle=(
                "Additional context is attached to generated "
                "targets but does not create independent targets."
            ),
            parent=self.investigation_container,
        )

        self.notes_card.setObjectName(
            "OsintNotesCard"
        )

        self.notes_card.set_variant(
            "default"
        )

        notes_container = QWidget(
            self.notes_card
        )

        notes_layout = QGridLayout(
            notes_container
        )

        notes_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        notes_layout.setHorizontalSpacing(
            16
        )

        notes_layout.setVerticalSpacing(
            8
        )

        self.keywords_input = self._create_list_input(
            notes_container,
            "keywords, one per line",
        )

        self.notes_input = QPlainTextEdit(
            notes_container
        )

        self.notes_input.setObjectName(
            "OsintNotesInput"
        )

        self.notes_input.setPlaceholderText(
            "Investigation notes, assumptions and context..."
        )

        self.notes_input.setMinimumHeight(
            120
        )

        notes_layout.addWidget(
            QLabel(
                "Keywords",
                notes_container,
            ),
            0,
            0,
        )

        notes_layout.addWidget(
            QLabel(
                "Notes",
                notes_container,
            ),
            0,
            1,
        )

        notes_layout.addWidget(
            self.keywords_input,
            1,
            0,
        )

        notes_layout.addWidget(
            self.notes_input,
            1,
            1,
        )

        notes_layout.setColumnStretch(
            0,
            1,
        )

        notes_layout.setColumnStretch(
            1,
            2,
        )

        self.notes_card.add_widget(
            notes_container
        )

        self.investigation_layout.addWidget(
            self.notes_card
        )

    # ==========================================================
    # Form actions
    # ==========================================================

    def _create_form_actions(
        self,
    ) -> None:
        """
        Create actions at the bottom of the investigation form.
        """

        self.form_actions_card = Card(
            parent=self.investigation_container
        )

        self.form_actions_card.setObjectName(
            "OsintFormActionsCard"
        )

        self.form_actions_card.set_variant(
            "elevated"
        )

        actions_container = QWidget(
            self.form_actions_card
        )

        actions_layout = QHBoxLayout(
            actions_container
        )

        actions_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        actions_layout.setSpacing(
            12
        )

        self.form_preview_button = QPushButton(
            "Preview Targets",
            actions_container,
        )

        self.form_preview_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.form_preview_button.clicked.connect(
            self.preview_requested.emit
        )

        self.form_connectors_button = QPushButton(
            "Find Compatible Connectors",
            actions_container,
        )

        self.form_connectors_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.form_connectors_button.clicked.connect(
            self.connectors_requested.emit
        )

        self.form_run_button = QPushButton(
            "Run Investigation",
            actions_container,
        )

        self.form_run_button.setProperty(
            "variant",
            "primary",
        )

        self.form_run_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.form_run_button.clicked.connect(
            self.run_requested.emit
        )

        actions_layout.addStretch(
            1
        )

        actions_layout.addWidget(
            self.form_preview_button
        )

        actions_layout.addWidget(
            self.form_connectors_button
        )

        actions_layout.addWidget(
            self.form_run_button
        )

        self.form_actions_card.add_widget(
            actions_container
        )

        self.investigation_layout.addWidget(
            self.form_actions_card
        )

    # ==========================================================
    # Results tab
    # ==========================================================

    def _create_results_tab(
        self,
    ) -> None:
        """
        Create results tab.
        """

        self.results_scroll = QScrollArea(
            self.tabs
        )

        self.results_scroll.setObjectName(
            "OsintResultsScroll"
        )

        self.results_scroll.setWidgetResizable(
            True
        )

        self.results_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.results_container = QWidget()

        self.results_container.setObjectName(
            "OsintResultsContainer"
        )

        self.results_layout = QVBoxLayout(
            self.results_container
        )

        self.results_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.results_layout.setSpacing(
            16
        )

        self._create_results_summary()
        self._create_results_placeholder()

        self.results_layout.addStretch(
            1
        )

        self.results_scroll.setWidget(
            self.results_container
        )

        self.tabs.addTab(
            self.results_scroll,
            "Results",
        )

    def _create_results_summary(
        self,
    ) -> None:
        """
        Create production results counters.
        """

        self.results_summary_card = Card(
            title="Investigation Results",
            subtitle=(
                "Separate confirmed findings from "
                "unverified discovery leads."
            ),
            parent=self.results_container,
        )

        self.results_summary_card.setObjectName(
            "OsintResultsSummaryCard"
        )

        self.results_summary_card.set_variant(
            "default"
        )

        statistics_container = QWidget(
            self.results_summary_card
        )

        statistics_layout = QHBoxLayout(
            statistics_container
        )

        statistics_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        statistics_layout.setSpacing(
            18
        )

        self.target_count_label = QLabel(
            "Targets: 0",
            statistics_container,
        )

        self.connector_count_label = QLabel(
            "Connectors: 0",
            statistics_container,
        )

        self.result_count_label = QLabel(
            "Findings: 0",
            statistics_container,
        )

        self.lead_count_label = QLabel(
            "Leads: 0",
            statistics_container,
        )

        statistics_layout.addWidget(
            self.target_count_label
        )

        statistics_layout.addWidget(
            self.connector_count_label
        )

        statistics_layout.addWidget(
            self.result_count_label
        )

        statistics_layout.addWidget(
            self.lead_count_label
        )

        statistics_layout.addStretch(
            1
        )

        self.results_summary_card.add_widget(
            statistics_container
        )

        self.results_layout.addWidget(
            self.results_summary_card
        )

    def _create_results_placeholder(
        self,
    ) -> None:
        """
        Create empty state and production results host.
        """

        self.results_placeholder_card = Card(
            title="No OSINT results",
            subtitle=(
                "Preview targets or run an investigation "
                "to populate this workspace."
            ),
            parent=self.results_container,
        )

        self.results_placeholder_card.setObjectName(
            "OsintResultsPlaceholderCard"
        )

        self.results_placeholder_card.set_variant(
            "default"
        )

        self.results_placeholder_label = QLabel(
            (
                "Run an investigation to display "
                "findings and discovery leads."
            ),
            self.results_placeholder_card,
        )

        self.results_placeholder_label.setWordWrap(
            True
        )

        self.results_placeholder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.results_placeholder_card.add_widget(
            self.results_placeholder_label
        )

        self.results_layout.addWidget(
            self.results_placeholder_card
        )

        self.results_content_container = QWidget(
            self.results_container
        )

        self.results_content_container.setObjectName(
            "OsintResultsContentContainer"
        )

        self.results_content_layout = QVBoxLayout(
            self.results_content_container
        )

        self.results_content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.results_content_layout.setSpacing(
            14
        )

        self.results_layout.addWidget(
            self.results_content_container
        )

        self.results_content_container.setVisible(
            False
        )

    def _clear_results_content(
        self,
    ) -> None:
        """
        Remove all previously rendered result widgets.
        """

        while (
            self.results_content_layout.count()
        ):

            item = (
                self.results_content_layout
                .takeAt(0)
            )

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _lead_platform_name(
        domain: object,
    ) -> str:
        """
        Return readable platform name.
        """

        value = str(
            domain
            or ""
        ).strip().lower()

        known = {
            "facebook.com": "Facebook",
            "instagram.com": "Instagram",
            "twitter.com": "Twitter / X",
            "x.com": "X",
            "linkedin.com": "LinkedIn",
            "vk.com": "VK",
            "tiktok.com": "TikTok",
            "youtube.com": "YouTube",
            "reddit.com": "Reddit",
            "telegram.me": "Telegram",
            "t.me": "Telegram",
            "pinterest.com": "Pinterest",
            "github.com": "GitHub",
            "gitlab.com": "GitLab",
        }

        if value in known:
            return known[
                value
            ]

        if not value:
            return "Search lead"

        first = value.split(
            "."
        )[0]

        return (
            first[:1].upper()
            + first[1:]
        )

    @staticmethod
    def _open_external_url(
        url: object,
    ) -> None:
        """
        Open only HTTP/HTTPS URLs in the system browser.
        """

        import webbrowser

        from urllib.parse import (
            urlparse,
        )

        value = str(
            url
            or ""
        ).strip()

        if not value:
            return

        try:

            parsed = urlparse(
                value
            )

        except Exception:
            return

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return

        if not parsed.netloc:
            return

        webbrowser.open(
            value,
            new=2,
        )

    def _create_url_button(
        self,
        text: str,
        url: object,
        parent: QWidget,
    ):
        """
        Create safe external URL button.
        """

        value = str(
            url
            or ""
        ).strip()

        if not value:
            return None

        button = QPushButton(
            text,
            parent,
        )

        button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        button.clicked.connect(
            lambda checked=False, target_url=value: (
                self._open_external_url(
                    target_url
                )
            )
        )

        return button

    @staticmethod
    def _toggle_lead_details(
        panel: QWidget,
        button: QPushButton,
        checked: bool,
    ) -> None:
        """
        Expand/collapse one lead.
        """

        panel.setVisible(
            bool(
                checked
            )
        )

        button.setText(
            "Hide details"
            if checked
            else "Details"
        )

    def _create_finding_widget(
        self,
        finding: dict[str, Any],
        parent: QWidget,
    ) -> QWidget:
        """
        Create compact confirmed/extracted finding.
        """

        row = QFrame(
            parent
        )

        row.setObjectName(
            "OsintFindingRow"
        )

        layout = QHBoxLayout(
            row
        )

        layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )

        layout.setSpacing(
            10
        )

        category = str(
            finding.get(
                "category"
            )
            or "finding"
        )

        value = str(
            finding.get(
                "value"
            )
            or ""
        )

        source = str(
            finding.get(
                "source"
            )
            or ""
        )

        parts = [
            f"<b>{category}</b>",
        ]

        if value:
            parts.append(
                value
            )

        if source:
            parts.append(
                f"Source: {source}"
            )

        label = QLabel(
            "<br>".join(
                parts
            ),
            row,
        )

        label.setTextFormat(
            Qt.TextFormat.RichText
        )

        label.setWordWrap(
            True
        )

        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout.addWidget(
            label,
            1,
        )

        source_button = self._create_url_button(
            "Open source",
            finding.get(
                "url"
            ),
            row,
        )

        if source_button is not None:

            layout.addWidget(
                source_button
            )

        return row

    def _create_lead_widget(
        self,
        item: dict[str, Any],
        parent: QWidget,
    ) -> QWidget:
        """
        Create compact lead with expandable query variants.
        """

        frame = QFrame(
            parent
        )

        frame.setObjectName(
            "OsintLeadRow"
        )

        outer = QVBoxLayout(
            frame
        )

        outer.setContentsMargins(
            10,
            8,
            10,
            8,
        )

        outer.setSpacing(
            8
        )

        normalized = item.get(
            "lead"
        )

        if not isinstance(
            normalized,
            dict,
        ):
            normalized = {}

        domain = normalized.get(
            "platform_domain"
        )

        platform = (
            self._lead_platform_name(
                domain
            )
        )

        source = str(
            normalized.get(
                "source"
            )
            or item.get(
                "source"
            )
            or ""
        )

        header = QWidget(
            frame
        )

        header_layout = QHBoxLayout(
            header
        )

        header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        header_layout.setSpacing(
            8
        )

        title = QLabel(
            (
                f"<b>{platform}</b>"
                + (
                    f" · {domain}"
                    if domain
                    else ""
                )
                + "<br>"
                + "<i>Unverified lead</i>"
                + (
                    f" · {source}"
                    if source
                    else ""
                )
            ),
            header,
        )

        title.setTextFormat(
            Qt.TextFormat.RichText
        )

        title.setWordWrap(
            True
        )

        header_layout.addWidget(
            title,
            1,
        )

        search_urls = normalized.get(
            "search_urls"
        )

        if not isinstance(
            search_urls,
            dict,
        ):
            search_urls = {}

        for engine, caption in (
            ("google", "Google"),
            ("bing", "Bing"),
            ("duckduckgo", "DuckDuckGo"),
        ):

            button = self._create_url_button(
                caption,
                search_urls.get(
                    engine
                ),
                header,
            )

            if button is not None:

                header_layout.addWidget(
                    button
                )

        details_button = QPushButton(
            "Details",
            header,
        )

        details_button.setCheckable(
            True
        )

        details_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        header_layout.addWidget(
            details_button
        )

        outer.addWidget(
            header
        )

        details_panel = QWidget(
            frame
        )

        details_layout = QVBoxLayout(
            details_panel
        )

        details_layout.setContentsMargins(
            14,
            4,
            0,
            0,
        )

        details_layout.setSpacing(
            6
        )

        variants = normalized.get(
            "variant_searches"
        )

        if not isinstance(
            variants,
            (
                list,
                tuple,
            ),
        ):
            variants = ()

        for variant in variants:

            if not isinstance(
                variant,
                dict,
            ):
                continue

            variant_row = QWidget(
                details_panel
            )

            variant_layout = QHBoxLayout(
                variant_row
            )

            variant_layout.setContentsMargins(
                0,
                0,
                0,
                0,
            )

            variant_layout.setSpacing(
                8
            )

            variant_label = str(
                variant.get(
                    "label"
                )
                or "Search"
            )

            query = str(
                variant.get(
                    "query"
                )
                or ""
            )

            query_label = QLabel(
                (
                    f"<b>{variant_label}</b>"
                    + (
                        f"<br><code>{query}</code>"
                        if query
                        else ""
                    )
                ),
                variant_row,
            )

            query_label.setTextFormat(
                Qt.TextFormat.RichText
            )

            query_label.setWordWrap(
                True
            )

            query_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            variant_layout.addWidget(
                query_label,
                1,
            )

            urls = variant.get(
                "search_urls"
            )

            if not isinstance(
                urls,
                dict,
            ):
                urls = {}

            for engine, caption in (
                ("google", "Google"),
                ("bing", "Bing"),
                ("duckduckgo", "DuckDuckGo"),
            ):

                button = self._create_url_button(
                    caption,
                    urls.get(
                        engine
                    ),
                    variant_row,
                )

                if button is not None:

                    variant_layout.addWidget(
                        button
                    )

            details_layout.addWidget(
                variant_row
            )

        if not variants:

            query = str(
                normalized.get(
                    "canonical_query"
                )
                or ""
            )

            if query:

                query_label = QLabel(
                    f"<code>{query}</code>",
                    details_panel,
                )

                query_label.setTextFormat(
                    Qt.TextFormat.RichText
                )

                query_label.setWordWrap(
                    True
                )

                query_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )

                details_layout.addWidget(
                    query_label
                )

        details_panel.setVisible(
            False
        )

        details_button.toggled.connect(
            lambda checked, panel=details_panel, button=details_button: (
                self._toggle_lead_details(
                    panel,
                    button,
                    checked,
                )
            )
        )

        outer.addWidget(
            details_panel
        )

        return frame

    def render_results(
        self,
        response: dict[str, Any],
    ) -> None:
        """
        Render production OSINT results using real Qt widgets.
        """

        if not isinstance(
            response,
            dict,
        ):
            response = {}

        self._workspace_state = dict(
            response
        )

        self._clear_results_content()

        target_results = response.get(
            "target_results"
        )

        if not isinstance(
            target_results,
            list,
        ):
            target_results = []

        if not target_results:

            self.results_placeholder_card.setVisible(
                True
            )

            self.results_content_container.setVisible(
                False
            )

            return

        self.results_placeholder_card.setVisible(
            False
        )

        self.results_content_container.setVisible(
            True
        )

        for target_index, target_result in enumerate(
            target_results,
            start=1,
        ):

            if not isinstance(
                target_result,
                dict,
            ):
                continue

            target = target_result.get(
                "target"
            )

            if not isinstance(
                target,
                dict,
            ):
                target = {}

            target_type = str(
                target.get(
                    "type"
                )
                or "target"
            )

            target_value = str(
                target.get(
                    "value"
                )
                or ""
            )

            target_card = Card(
                title=(
                    f"Target {target_index} · "
                    f"{target_type}"
                ),
                subtitle=target_value,
                parent=self.results_content_container,
            )

            target_card.setObjectName(
                "OsintTargetResultCard"
            )

            target_card.set_variant(
                "default"
            )

            connector_results = (
                target_result.get(
                    "results"
                )
            )

            if not isinstance(
                connector_results,
                list,
            ):
                connector_results = []

            for result in connector_results:

                if not isinstance(
                    result,
                    dict,
                ):
                    continue

                connector_name = str(
                    result.get(
                        "connector"
                    )
                    or "Unknown connector"
                )

                status = str(
                    result.get(
                        "status"
                    )
                    or "unknown"
                )

                finding_count = int(
                    result.get(
                        "total_findings"
                    )
                    or 0
                )

                lead_count = int(
                    result.get(
                        "total_leads"
                    )
                    or 0
                )

                connector_card = Card(
                    title=connector_name,
                    subtitle=(
                        f"Status: {status} · "
                        f"Findings: {finding_count} · "
                        f"Leads: {lead_count}"
                    ),
                    parent=target_card,
                )

                connector_card.setObjectName(
                    "OsintConnectorResultCard"
                )

                connector_card.set_variant(
                    "default"
                )

                error = result.get(
                    "error"
                )

                if error:

                    error_label = QLabel(
                        (
                            "<b>Error:</b> "
                            + str(
                                error
                            )
                        ),
                        connector_card,
                    )

                    error_label.setWordWrap(
                        True
                    )

                    connector_card.add_widget(
                        error_label
                    )

                items = result.get(
                    "findings"
                )

                if not isinstance(
                    items,
                    list,
                ):
                    items = []

                findings = [
                    item
                    for item in items
                    if (
                        isinstance(
                            item,
                            dict,
                        )
                        and item.get(
                            "kind"
                        )
                        != "lead"
                    )
                ]

                leads = [
                    item
                    for item in items
                    if (
                        isinstance(
                            item,
                            dict,
                        )
                        and item.get(
                            "kind"
                        )
                        == "lead"
                    )
                ]

                findings_title = QLabel(
                    (
                        "<b>"
                        f"Findings ({len(findings)})"
                        "</b>"
                    ),
                    connector_card,
                )

                findings_title.setTextFormat(
                    Qt.TextFormat.RichText
                )

                connector_card.add_widget(
                    findings_title
                )

                if findings:

                    for finding in findings:

                        connector_card.add_widget(
                            self._create_finding_widget(
                                finding,
                                connector_card,
                            )
                        )

                else:

                    connector_card.add_widget(
                        QLabel(
                            "No confirmed/extracted findings.",
                            connector_card,
                        )
                    )

                leads_title = QLabel(
                    (
                        "<b>"
                        f"Leads ({len(leads)})"
                        "</b>"
                    ),
                    connector_card,
                )

                leads_title.setTextFormat(
                    Qt.TextFormat.RichText
                )

                connector_card.add_widget(
                    leads_title
                )

                if leads:

                    groups: dict[
                        str,
                        list[dict[str, Any]],
                    ] = {}

                    for lead in leads:

                        normalized = lead.get(
                            "lead"
                        )

                        if not isinstance(
                            normalized,
                            dict,
                        ):
                            normalized = {}

                        metadata = lead.get(
                            "metadata"
                        )

                        if not isinstance(
                            metadata,
                            dict,
                        ):
                            metadata = {}

                        category = str(
                            normalized.get(
                                "category"
                            )
                            or metadata.get(
                                "category"
                            )
                            or lead.get(
                                "category"
                            )
                            or "Search"
                        )

                        groups.setdefault(
                            category,
                            [],
                        ).append(
                            lead
                        )

                    for category in sorted(
                        groups,
                        key=str.casefold,
                    ):

                        category_label = QLabel(
                            (
                                "<b>"
                                f"{category} "
                                f"({len(groups[category])})"
                                "</b>"
                            ),
                            connector_card,
                        )

                        category_label.setTextFormat(
                            Qt.TextFormat.RichText
                        )

                        connector_card.add_widget(
                            category_label
                        )

                        for lead in groups[
                            category
                        ]:

                            connector_card.add_widget(
                                self._create_lead_widget(
                                    lead,
                                    connector_card,
                                )
                            )

                else:

                    connector_card.add_widget(
                        QLabel(
                            "No discovery leads.",
                            connector_card,
                        )
                    )

                target_card.add_widget(
                    connector_card
                )

            self.results_content_layout.addWidget(
                target_card
            )

    # ==========================================================
    # History tab
    # ==========================================================

    def _create_history_tab(
        self,
    ) -> None:
        """
        Create future investigation history tab.
        """

        self.history_container = QWidget(
            self.tabs
        )

        self.history_layout = QVBoxLayout(
            self.history_container
        )

        self.history_layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.history_layout.setSpacing(
            16
        )

        self.history_card = Card(
            title="Investigation History",
            subtitle=(
                "Saved and previously executed investigations "
                "will be displayed here in a later stage."
            ),
            parent=self.history_container,
        )

        self.history_card.set_variant(
            "default"
        )

        history_label = QLabel(
            (
                "History storage is not connected yet.\n\n"
                "Current OSINT execution remains stateless."
            ),
            self.history_card,
        )

        history_label.setWordWrap(
            True
        )

        self.history_card.add_widget(
            history_label
        )

        self.history_layout.addWidget(
            self.history_card
        )

        self.history_layout.addStretch(
            1
        )

        self.tabs.addTab(
            self.history_container,
            "History",
        )

    # ==========================================================
    # Form data
    # ==========================================================

    def form_data(
        self,
    ) -> dict[str, Any]:
        """
        Return all investigation form data.

        List values remain text here. OsintController is
        responsible for normalization and request creation.
        """

        birth_date: str | None = None

        if self.birth_date_enabled.isChecked():

            birth_date = (
                self.birth_date_input
                .date()
                .toString(
                    "yyyy-MM-dd"
                )
            )

        return {
            "case_id": self._line_text(
                self.case_id_input
            ),
            "title": self._line_text(
                self.title_input
            ),
            "description": (
                self.description_input
                .toPlainText()
                .strip()
            ),
            "first_name": self._line_text(
                self.first_name_input
            ),
            "middle_name": self._line_text(
                self.middle_name_input
            ),
            "last_name": self._line_text(
                self.last_name_input
            ),
            "birth_date": birth_date,
            "usernames": (
                self.usernames_input
                .toPlainText()
            ),
            "emails": (
                self.emails_input
                .toPlainText()
            ),
            "phones": (
                self.phones_input
                .toPlainText()
            ),
            "address": self._line_text(
                self.address_input
            ),
            "city": self._line_text(
                self.city_input
            ),
            "region": self._line_text(
                self.region_input
            ),
            "postal_code": self._line_text(
                self.postal_code_input
            ),
            "country": self._line_text(
                self.country_input
            ),
            "organizations": (
                self.organizations_input
                .toPlainText()
            ),
            "domains": (
                self.domains_input
                .toPlainText()
            ),
            "urls": (
                self.urls_input
                .toPlainText()
            ),
            "ip_addresses": (
                self.ip_addresses_input
                .toPlainText()
            ),
            "hashes": (
                self.hashes_input
                .toPlainText()
            ),
            "file_paths": (
                self.file_paths_input
                .toPlainText()
            ),
            "image_paths": (
                self.image_paths_input
                .toPlainText()
            ),
            "keywords": (
                self.keywords_input
                .toPlainText()
            ),
            "notes": (
                self.notes_input
                .toPlainText()
                .strip()
            ),
            "selected_connectors": (
                self.selected_connectors_input
                .toPlainText()
            ),
            "timeout": self.timeout_input.value(),
            "use_cache": (
                self.use_cache_checkbox
                .isChecked()
            ),
            "save_raw_output": (
                self.save_raw_output_checkbox
                .isChecked()
            ),
            "include_metadata": (
                self.include_metadata_checkbox
                .isChecked()
            ),
            "include_related": (
                self.include_related_checkbox
                .isChecked()
            ),
        }

    def set_form_data(
        self,
        data: dict[str, Any] | None,
    ) -> None:
        """
        Populate the form from a dictionary.
        """

        normalized_data = (
            data
            if isinstance(
                data,
                dict,
            )
            else {}
        )

        self._set_line_value(
            self.case_id_input,
            normalized_data.get("case_id"),
        )

        self._set_line_value(
            self.title_input,
            normalized_data.get("title"),
        )

        self.description_input.setPlainText(
            self._string_value(
                normalized_data.get(
                    "description"
                )
            )
        )

        self._set_line_value(
            self.first_name_input,
            normalized_data.get("first_name"),
        )

        self._set_line_value(
            self.middle_name_input,
            normalized_data.get("middle_name"),
        )

        self._set_line_value(
            self.last_name_input,
            normalized_data.get("last_name"),
        )

        self._set_birth_date(
            normalized_data.get(
                "birth_date"
            )
        )

        self._set_plain_value(
            self.usernames_input,
            normalized_data.get("usernames"),
        )

        self._set_plain_value(
            self.emails_input,
            normalized_data.get("emails"),
        )

        self._set_plain_value(
            self.phones_input,
            normalized_data.get("phones"),
        )

        self._set_line_value(
            self.address_input,
            normalized_data.get("address"),
        )

        self._set_line_value(
            self.city_input,
            normalized_data.get("city"),
        )

        self._set_line_value(
            self.region_input,
            normalized_data.get("region"),
        )

        self._set_line_value(
            self.postal_code_input,
            normalized_data.get("postal_code"),
        )

        self._set_line_value(
            self.country_input,
            normalized_data.get("country"),
        )

        self._set_plain_value(
            self.organizations_input,
            normalized_data.get("organizations"),
        )

        self._set_plain_value(
            self.domains_input,
            normalized_data.get("domains"),
        )

        self._set_plain_value(
            self.urls_input,
            normalized_data.get("urls"),
        )

        self._set_plain_value(
            self.ip_addresses_input,
            normalized_data.get("ip_addresses"),
        )

        self._set_plain_value(
            self.hashes_input,
            normalized_data.get("hashes"),
        )

        self._set_plain_value(
            self.file_paths_input,
            normalized_data.get("file_paths"),
        )

        self._set_plain_value(
            self.image_paths_input,
            normalized_data.get("image_paths"),
        )

        self._set_plain_value(
            self.keywords_input,
            normalized_data.get("keywords"),
        )

        self.notes_input.setPlainText(
            self._string_value(
                normalized_data.get(
                    "notes"
                )
            )
        )

        self._set_plain_value(
            self.selected_connectors_input,
            normalized_data.get(
                "selected_connectors"
            ),
        )

        timeout = normalized_data.get(
            "timeout",
            300,
        )

        try:

            normalized_timeout = int(
                timeout
            )

        except (
            TypeError,
            ValueError,
        ):

            normalized_timeout = 300

        self.timeout_input.setValue(
            max(
                1,
                min(
                    3600,
                    normalized_timeout,
                ),
            )
        )

        self.use_cache_checkbox.setChecked(
            bool(
                normalized_data.get(
                    "use_cache",
                    True,
                )
            )
        )

        self.save_raw_output_checkbox.setChecked(
            bool(
                normalized_data.get(
                    "save_raw_output",
                    False,
                )
            )
        )

        self.include_metadata_checkbox.setChecked(
            bool(
                normalized_data.get(
                    "include_metadata",
                    True,
                )
            )
        )

        self.include_related_checkbox.setChecked(
            bool(
                normalized_data.get(
                    "include_related",
                    True,
                )
            )
        )

    def clear_form(
        self,
    ) -> None:
        """
        Clear all investigation form fields.
        """

        line_inputs = (
            self.case_id_input,
            self.title_input,
            self.first_name_input,
            self.middle_name_input,
            self.last_name_input,
            self.country_input,
            self.region_input,
            self.city_input,
            self.postal_code_input,
            self.address_input,
        )

        for line_input in line_inputs:

            line_input.clear()

        plain_inputs = (
            self.description_input,
            self.usernames_input,
            self.emails_input,
            self.phones_input,
            self.organizations_input,
            self.domains_input,
            self.urls_input,
            self.ip_addresses_input,
            self.hashes_input,
            self.file_paths_input,
            self.image_paths_input,
            self.keywords_input,
            self.notes_input,
            self.selected_connectors_input,
        )

        for plain_input in plain_inputs:

            plain_input.clear()

        self.birth_date_enabled.setChecked(
            False
        )

        self.birth_date_input.setDate(
            QDate.currentDate()
        )

        self.timeout_input.setValue(
            300
        )

        self.use_cache_checkbox.setChecked(
            True
        )

        self.save_raw_output_checkbox.setChecked(
            False
        )

        self.include_metadata_checkbox.setChecked(
            True
        )

        self.include_related_checkbox.setChecked(
            True
        )

    # ==========================================================
    # Workspace state
    # ==========================================================

    def set_workspace_state(
        self,
        state: dict[str, Any] | None,
    ) -> None:
        """
        Display initial OSINT workspace state.
        """

        normalized_state = (
            state
            if isinstance(
                state,
                dict,
            )
            else {}
        )

        self._workspace_state = dict(
            normalized_state
        )

        available_connectors = (
            normalized_state.get(
                "available_connectors"
            )
            or normalized_state.get(
                "connectors"
            )
            or []
        )

        if not isinstance(
            available_connectors,
            (
                list,
                tuple,
                set,
            ),
        ):

            available_connectors = []

        connector_count = normalized_state.get(
            "connector_count"
        )

        if not isinstance(
            connector_count,
            int,
        ):

            connector_count = len(
                available_connectors
            )

        self._connector_count = max(
            0,
            int(
                connector_count
            ),
        )

        self._status_mode = "loaded"
        self._status_message = None
        self._status_connector_count = (
            self._connector_count
        )

        self._update_summary_labels()
        self._update_status_label()

    def workspace_state(
        self,
    ) -> dict[str, Any]:
        """
        Return the currently displayed workspace state.
        """

        return dict(
            self._workspace_state
        )

    # ==========================================================
    # Summary
    # ==========================================================

    def set_summary_counts(
        self,
        target_count: int = 0,
        connector_count: int = 0,
        result_count: int = 0,
        lead_count: int = 0,
    ) -> None:
        """
        Update results summary counters.
        """

        self._target_count = max(
            0,
            int(
                target_count
            ),
        )

        self._connector_count = max(
            0,
            int(
                connector_count
            ),
        )

        self._result_count = max(
            0,
            int(
                result_count
            ),
        )

        self._lead_count = max(
            0,
            int(
                lead_count
            ),
        )

        self._update_summary_labels()

    # ==========================================================
    # Status
    # ==========================================================

    def set_status(
        self,
        message: str,
    ) -> None:
        """
        Set workspace status message.
        """

        normalized_message = str(
            message
        ).strip()

        self._status_mode = (
            "custom"
            if normalized_message
            else "ready"
        )

        self._status_message = (
            normalized_message
            or None
        )

        self._update_status_label()

    def set_error(
        self,
        message: str,
    ) -> None:
        """
        Display an OSINT workspace error.
        """

        normalized_message = str(
            message
        ).strip()

        self._status_mode = "error"
        self._status_message = (
            normalized_message
            or None
        )

        self._update_status_label()

    # ==========================================================
    # Loading
    # ==========================================================

    def set_loading(
        self,
        loading: bool,
        message: str | None = None,
    ) -> None:
        """
        Update workspace controls during loading.
        """

        self._loading = bool(
            loading
        )

        controls = (
            self.preview_button,
            self.connectors_button,
            self.run_button,
            self.refresh_button,
            self.clear_button,
            self.form_preview_button,
            self.form_connectors_button,
            self.form_run_button,
            self.add_files_button,
            self.add_images_button,
        )

        for control in controls:

            control.setEnabled(
                not self._loading
            )

        normalized_message = (
            str(
                message
            ).strip()
            if message is not None
            else ""
        )

        if self._loading:

            self._status_mode = "loading"
            self._status_message = (
                normalized_message
                or None
            )

        elif normalized_message:

            self._status_mode = "custom"
            self._status_message = normalized_message

        elif self._status_mode == "loading":

            self._status_mode = "ready"
            self._status_message = None

        self._update_action_labels()
        self._update_status_label()

    def is_loading(
        self,
    ) -> bool:
        """
        Return whether the workspace is loading.
        """

        return self._loading

    # ==========================================================
    # Navigation
    # ==========================================================

    def show_investigation_tab(
        self,
    ) -> None:

        self.tabs.setCurrentWidget(
            self.investigation_scroll
        )

    def show_results_tab(
        self,
    ) -> None:

        self.tabs.setCurrentWidget(
            self.results_scroll
        )

    def show_history_tab(
        self,
    ) -> None:

        self.tabs.setCurrentWidget(
            self.history_container
        )

    # ==========================================================
    # Clear
    # ==========================================================

    def clear_workspace(
        self,
    ) -> None:
        """
        Clear form and displayed OSINT state.
        """

        self._workspace_state = {}

        self.clear_form()

        self.set_summary_counts()

        self._status_mode = "cleared"
        self._status_message = None
        self._update_status_label()

        self.show_investigation_tab()

    # ==========================================================
    # File dialogs
    # ==========================================================

    def _select_files(
        self,
    ) -> None:
        """
        Select one or more local files.
        """

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.translate(
                "osint_workspace.dialog.select_files",
                default="Select files",
            ),
            "",
            self.translate(
                "osint_workspace.dialog.all_files_filter",
                default="All files (*.*)",
            ),
        )

        self._append_paths(
            self.file_paths_input,
            paths,
        )

    def _select_images(
        self,
    ) -> None:
        """
        Select one or more local images.
        """

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.translate(
                "osint_workspace.dialog.select_images",
                default="Select images",
            ),
            "",
            self.translate(
                "osint_workspace.dialog.images_filter",
                default=(
                    "Images (*.png *.jpg *.jpeg *.webp "
                    "*.bmp *.gif *.tif *.tiff);;"
                    "All files (*.*)"
                ),
            ),
        )

        self._append_paths(
            self.image_paths_input,
            paths,
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _configure_form_layout(
        layout: QFormLayout,
    ) -> None:

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setHorizontalSpacing(
            16
        )

        layout.setVerticalSpacing(
            10
        )

        layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

    @staticmethod
    def _create_line_input(
        parent: QWidget,
        placeholder: str,
    ) -> QLineEdit:

        line_input = QLineEdit(
            parent
        )

        line_input.setPlaceholderText(
            placeholder
        )

        return line_input

    @staticmethod
    def _create_list_input(
        parent: QWidget,
        placeholder: str,
    ) -> QPlainTextEdit:

        plain_input = QPlainTextEdit(
            parent
        )

        plain_input.setPlaceholderText(
            placeholder
        )

        plain_input.setMinimumHeight(
            110
        )

        return plain_input

    @staticmethod
    def _line_text(
        line_input: QLineEdit,
    ) -> str:

        return (
            line_input
            .text()
            .strip()
        )

    @staticmethod
    def _string_value(
        value: Any,
    ) -> str:

        if value is None:

            return ""

        return str(
            value
        )

    @classmethod
    def _set_line_value(
        cls,
        line_input: QLineEdit,
        value: Any,
    ) -> None:

        line_input.setText(
            cls._string_value(
                value
            )
        )

    @classmethod
    def _set_plain_value(
        cls,
        plain_input: QPlainTextEdit,
        value: Any,
    ) -> None:

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            text = "\n".join(
                cls._string_value(
                    item
                )
                for item in value
                if item is not None
            )

        else:

            text = cls._string_value(
                value
            )

        plain_input.setPlainText(
            text
        )

    def _set_birth_date(
        self,
        value: Any,
    ) -> None:

        if value is None or value == "":

            self.birth_date_enabled.setChecked(
                False
            )

            self.birth_date_input.setDate(
                QDate.currentDate()
            )

            return

        if isinstance(
            value,
            date,
        ):

            parsed_date = QDate(
                value.year,
                value.month,
                value.day,
            )

        else:

            parsed_date = QDate.fromString(
                str(
                    value
                ),
                "yyyy-MM-dd",
            )

        if not parsed_date.isValid():

            self.birth_date_enabled.setChecked(
                False
            )

            return

        self.birth_date_input.setDate(
            parsed_date
        )

        self.birth_date_enabled.setChecked(
            True
        )

    @staticmethod
    def _append_paths(
        input_widget: QPlainTextEdit,
        paths: list[str],
    ) -> None:

        if not paths:

            return

        existing_lines = [
            line.strip()
            for line in (
                input_widget
                .toPlainText()
                .splitlines()
            )
            if line.strip()
        ]

        known_paths = set(
            existing_lines
        )

        for path in paths:

            normalized_path = str(
                path
            ).strip()

            if (
                normalized_path
                and normalized_path
                not in known_paths
            ):

                existing_lines.append(
                    normalized_path
                )

                known_paths.add(
                    normalized_path
                )

        input_widget.setPlainText(
            "\n".join(
                existing_lines
            )
        )