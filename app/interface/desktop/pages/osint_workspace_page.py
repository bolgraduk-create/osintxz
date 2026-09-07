"""
OSINT workspace page.

Responsible for:

- connecting OsintWorkspaceView with OsintController
- loading OSINT workspace state
- handling target preview
- handling compatible connector discovery
- handling OSINT investigation execution
- formatting controller responses for presentation
- displaying operation errors

Does NOT:

- execute connectors directly
- access the database directly
- create OSINT targets
- contain OSINT business logic
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QMessageBox,
    QVBoxLayout,
)

from app.interface.desktop.pages.base_page import (
    BasePage,
)

from app.interface.desktop.views.osint_workspace_view import (
    OsintWorkspaceView,
)


class OsintWorkspacePage(BasePage):
    """
    Desktop page for the OSINT workspace.

    The page acts as a thin coordinator between
    OsintWorkspaceView and OsintController.
    """

    def __init__(
        self,
        container,
    ) -> None:

        self.container = container

        super().__init__(
            "OSINT Workspace"
        )

        self._load_workspace_state()

    # ==========================================================
    # UI
    # ==========================================================

    def _setup_ui(
        self,
    ) -> None:
        """
        Create the OSINT workspace page.
        """

        self.setObjectName(
            "OsintWorkspacePage"
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
            0
        )

        self.workspace_view = OsintWorkspaceView(
            parent=self
        )

        self._connect_signals()

        self.main_layout.addWidget(
            self.workspace_view
        )

    def _connect_signals(
        self,
    ) -> None:
        """
        Connect workspace actions with page handlers.
        """

        self.workspace_view.preview_requested.connect(
            self._preview_targets
        )

        self.workspace_view.connectors_requested.connect(
            self._find_compatible_connectors
        )

        self.workspace_view.run_requested.connect(
            self._run_investigation
        )

        self.workspace_view.refresh_requested.connect(
            self._load_workspace_state
        )

        self.workspace_view.clear_requested.connect(
            self._clear_workspace
        )

    # ==========================================================
    # Public refresh
    # ==========================================================

    def refresh(
        self,
    ) -> None:
        """
        Public page refresh method.
        """

        self._load_workspace_state()

    # ==========================================================
    # Workspace state
    # ==========================================================

    def _load_workspace_state(
        self,
    ) -> None:
        """
        Load current OSINT workspace state.
        """

        self.workspace_view.set_loading(
            True,
            "Loading OSINT workspace...",
        )

        try:

            state = (
                self.container
                .osint_controller
                .get_workspace_state()
            )

        except Exception as exc:

            self.workspace_view.set_error(
                str(
                    exc
                )
            )

            QMessageBox.critical(
                self,
                "OSINT Workspace",
                (
                    "The OSINT workspace state "
                    "could not be loaded.\n\n"
                    f"{exc}"
                ),
            )

            return

        finally:

            self.workspace_view.set_loading(
                False
            )

        if not isinstance(
            state,
            dict,
        ):

            state = {}

        self.workspace_view.set_workspace_state(
            state
        )

    # ==========================================================
    # Target preview
    # ==========================================================

    def _preview_targets(
        self,
    ) -> None:
        """
        Build and display OSINT targets without executing connectors.
        """

        form_data = (
            self.workspace_view
            .form_data()
        )

        self.workspace_view.set_loading(
            True,
            "Building OSINT targets...",
        )

        try:

            response = (
                self.container
                .osint_controller
                .preview_targets(
                    form_data
                )
            )

        except Exception as exc:

            self._show_operation_error(
                title="Target preview failed",
                exception=exc,
            )

            return

        finally:

            self.workspace_view.set_loading(
                False
            )

        # ==========================================================
        # Normalize production investigation response
        #
        # OsintWorkspaceService returns:
        #
        # target_results[]
        #     -> results[]
        #         -> findings[]
        #
        # Older UI code expected top-level results/findings and
        # therefore reported zero findings for valid executions.
        # ==========================================================

        targets = self._extract_collection(
            response=response,
            possible_keys=(
                "targets",
                "generated_targets",
            ),
        )

        target_results = []

        if isinstance(
            response,
            dict,
        ):

            raw_target_results = response.get(
                "target_results",
                [],
            )

            if isinstance(
                raw_target_results,
                (list, tuple),
            ):

                target_results = list(
                    raw_target_results
                )


        # Flatten connector executions.

        results = []

        for target_result in target_results:

            if not isinstance(
                target_result,
                dict,
            ):
                continue

            nested_results = target_result.get(
                "results",
                [],
            )

            if not isinstance(
                nested_results,
                (list, tuple),
            ):
                continue

            for connector_result in nested_results:

                if isinstance(
                    connector_result,
                    dict,
                ):
                    results.append(
                        connector_result
                    )


        # Backward compatibility with an older / direct response.

        if not results:

            results = self._extract_collection(
                response=response,
                possible_keys=(
                    "results",
                    "connector_results",
                    "items",
                ),
            )


        # Flatten actual OSINT findings.

        findings = []

        for connector_result in results:

            if not isinstance(
                connector_result,
                dict,
            ):
                continue

            nested_findings = connector_result.get(
                "findings",
                [],
            )

            if not isinstance(
                nested_findings,
                (list, tuple),
            ):
                continue

            for finding in nested_findings:

                if isinstance(
                    finding,
                    dict,
                ):
                    findings.append(
                        finding
                    )


        # Connector names are also nested in connector results.

        connector_names = []

        seen_connector_names = set()

        for connector_result in results:

            if not isinstance(
                connector_result,
                dict,
            ):
                continue

            connector_name = str(
                connector_result.get(
                    "connector",
                    "",
                )
            ).strip()

            if not connector_name:
                continue

            normalized_name = (
                connector_name.casefold()
            )

            if (
                normalized_name
                in seen_connector_names
            ):
                continue

            seen_connector_names.add(
                normalized_name
            )

            connector_names.append(
                connector_name
            )


        summary = {}

        if isinstance(
            response,
            dict,
        ):

            raw_summary = response.get(
                "summary"
            )

            if isinstance(
                raw_summary,
                dict,
            ):
                summary = raw_summary


        target_count = self._extract_count(
            response=response,
            possible_keys=(
                "target_count",
                "targets_count",
            ),
            fallback=len(
                targets
            ),
        )


        # For an investigation, connector_runs from the service
        # is more authoritative than a nonexistent top-level
        # connectors array.

        try:
            connector_count = int(
                summary.get(
                    "connector_runs",
                    len(results),
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            connector_count = len(
                results
            )


        # "Results" in the UI means actual findings, not the
        # number of connector executions.

        try:
            result_count = int(
                summary.get(
                    "total_findings",
                    len(findings),
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            result_count = len(
                findings
            )


        self.workspace_view.set_summary_counts(
            target_count=target_count,
            connector_count=connector_count,
            result_count=0,
        )

        self.workspace_view.results_placeholder_label.setText(
            self._format_targets(
                targets
            )
        )

        self.workspace_view.set_status(
            (
                f"Target preview completed · "
                f"{target_count} targets generated"
            )
        )

        self.workspace_view.show_results_tab()

    # ==========================================================
    # Compatible connectors
    # ==========================================================

    def _find_compatible_connectors(
        self,
    ) -> None:
        """
        Find connectors compatible with the current form targets.
        """

        form_data = (
            self.workspace_view
            .form_data()
        )

        self.workspace_view.set_loading(
            True,
            "Finding compatible connectors...",
        )

        try:

            response = (
                self.container
                .osint_controller
                .get_compatible_connectors(
                    form_data
                )
            )

        except Exception as exc:

            self._show_operation_error(
                title="Connector discovery failed",
                exception=exc,
            )

            return

        finally:

            self.workspace_view.set_loading(
                False
            )

        connectors = self._extract_collection(
            response=response,
            possible_keys=(
                "connectors",
                "compatible_connectors",
                "items",
                "results",
            ),
        )

        connector_count = len(
            connectors
        )

        self.workspace_view.set_summary_counts(
            target_count=0,
            connector_count=connector_count,
            result_count=0,
        )

        self.workspace_view.results_placeholder_label.setText(
            self._format_connectors(
                connectors
            )
        )

        self.workspace_view.set_status(
            (
                "Connector discovery completed · "
                f"{connector_count} compatible connectors"
            )
        )

        self.workspace_view.show_results_tab()

    # ==========================================================
    # Investigation execution
    # ==========================================================

    def _run_investigation(
        self,
    ) -> None:
        """
        Execute investigation using canonical nested response.
        """

        form_data = (
            self.workspace_view
            .form_data()
        )

        confirmation = QMessageBox.question(
            self,
            "Run OSINT investigation",
            (
                "Run all selected or compatible OSINT connectors "
                "for the entered targets?"
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            ),
            QMessageBox.StandardButton.Yes,
        )

        if (
            confirmation
            != QMessageBox.StandardButton.Yes
        ):
            return

        self.workspace_view.set_loading(
            True,
            "Running OSINT investigation...",
        )

        try:

            response = (
                self.container
                .osint_controller
                .run_investigation(
                    form_data
                )
            )

        except Exception as exc:

            self._show_operation_error(
                title="OSINT investigation failed",
                exception=exc,
            )

            return

        finally:

            self.workspace_view.set_loading(
                False
            )

        if not isinstance(
            response,
            dict,
        ):
            response = {}

        summary = response.get(
            "summary"
        )

        if not isinstance(
            summary,
            dict,
        ):
            summary = {}

        targets = response.get(
            "targets"
        )

        if not isinstance(
            targets,
            list,
        ):
            targets = []

        target_count = int(
            response.get(
                "target_count"
            )
            or len(
                targets
            )
        )

        connector_count = int(
            summary.get(
                "connector_runs"
            )
            or 0
        )

        finding_count = int(
            summary.get(
                "total_findings"
            )
            or 0
        )

        lead_count = int(
            summary.get(
                "total_leads"
            )
            or 0
        )

        self.workspace_view.set_summary_counts(
            target_count=target_count,
            connector_count=connector_count,
            result_count=finding_count,
            lead_count=lead_count,
        )

        self.workspace_view.render_results(
            response
        )

        self.workspace_view.set_status(
            (
                "OSINT investigation completed · "
                f"{finding_count} findings · "
                f"{lead_count} leads"
            )
        )

        self.workspace_view.show_results_tab()

    # ==========================================================
    # Clear
    # ==========================================================

    def _clear_workspace(
        self,
    ) -> None:
        """
        Clear the current form and displayed results.
        """

        has_form_data = self._has_meaningful_form_data(
            self.workspace_view.form_data()
        )

        if has_form_data:

            confirmation = QMessageBox.question(
                self,
                "Clear OSINT workspace",
                (
                    "Clear all entered investigation data "
                    "and displayed results?"
                ),
                (
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                ),
                QMessageBox.StandardButton.No,
            )

            if (
                confirmation
                != QMessageBox.StandardButton.Yes
            ):

                return

        self.workspace_view.clear_workspace()

        self.workspace_view.results_placeholder_label.setText(
            (
                "The results workspace will contain:\n\n"
                "• Generated targets\n"
                "• Compatible connectors\n"
                "• Connector execution status\n"
                "• Findings\n"
                "• Errors and diagnostic output\n"
                "• Raw result metadata"
            )
        )

    # ==========================================================
    # Error handling
    # ==========================================================

    def _show_operation_error(
        self,
        title: str,
        exception: Exception,
    ) -> None:
        """
        Display an operation error in both the view and dialog.
        """

        message = str(
            exception
        ).strip()

        if not message:

            message = (
                exception.__class__.__name__
            )

        self.workspace_view.set_error(
            message
        )

        QMessageBox.critical(
            self,
            title,
            message,
        )

    # ==========================================================
    # Response extraction
    # ==========================================================

    @classmethod
    def _extract_collection(
        cls,
        response: Any,
        possible_keys: tuple[str, ...],
    ) -> list[Any]:
        """
        Extract a list-like value from a controller response.
        """

        if isinstance(
            response,
            list,
        ):

            return list(
                response
            )

        if isinstance(
            response,
            tuple,
        ):

            return list(
                response
            )

        if isinstance(
            response,
            set,
        ):

            return list(
                response
            )

        if not isinstance(
            response,
            dict,
        ):

            return []

        for key in possible_keys:

            value = response.get(
                key
            )

            normalized = (
                cls._normalize_collection(
                    value
                )
            )

            if normalized:

                return normalized

        data = response.get(
            "data"
        )

        if isinstance(
            data,
            dict,
        ):

            for key in possible_keys:

                value = data.get(
                    key
                )

                normalized = (
                    cls._normalize_collection(
                        value
                    )
                )

                if normalized:

                    return normalized

        return []

    @staticmethod
    def _normalize_collection(
        value: Any,
    ) -> list[Any]:
        """
        Normalize a possible collection.
        """

        if isinstance(
            value,
            list,
        ):

            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):

            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):

            return list(
                value
            )

        if value is None:

            return []

        return []

    @classmethod
    def _extract_count(
        cls,
        response: Any,
        possible_keys: tuple[str, ...],
        fallback: int = 0,
    ) -> int:
        """
        Extract a non-negative count from a response.
        """

        if isinstance(
            response,
            dict,
        ):

            for key in possible_keys:

                if key not in response:

                    continue

                normalized = cls._safe_int(
                    response.get(
                        key
                    )
                )

                if normalized is not None:

                    return normalized

            data = response.get(
                "data"
            )

            if isinstance(
                data,
                dict,
            ):

                for key in possible_keys:

                    if key not in data:

                        continue

                    normalized = cls._safe_int(
                        data.get(
                            key
                        )
                    )

                    if normalized is not None:

                        return normalized

        return max(
            0,
            fallback,
        )

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int | None:
        """
        Convert a value into a non-negative integer.
        """

        try:

            return max(
                0,
                int(
                    value
                ),
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    @staticmethod
    def _normalize_direct_response(
        response: Any,
    ) -> list[Any]:
        """
        Treat a direct non-empty response as one displayed result.
        """

        if response is None:

            return []

        if isinstance(
            response,
            dict,
        ):

            if not response:

                return []

            return [
                response
            ]

        if isinstance(
            response,
            (
                list,
                tuple,
                set,
            ),
        ):

            return list(
                response
            )

        return [
            response
        ]

    # ==========================================================
    # Formatting
    # ==========================================================

    @classmethod
    def _format_targets(
        cls,
        targets: list[Any],
    ) -> str:
        """
        Convert generated targets into readable text.
        """

        if not targets:

            return (
                "No targets were generated.\n\n"
                "Enter at least one supported value, such as "
                "a username, email, phone, domain, URL, IP address "
                "or person name."
            )

        lines = [
            "Generated OSINT targets",
            "",
        ]

        for index, target in enumerate(
            targets,
            start=1,
        ):

            lines.append(
                cls._format_target_line(
                    index=index,
                    target=target,
                )
            )

        return "\n".join(
            lines
        )

    @classmethod
    def _format_target_line(
        cls,
        index: int,
        target: Any,
    ) -> str:
        """
        Format one target.
        """

        if isinstance(
            target,
            dict,
        ):

            target_type = (
                target.get("target_type")
                or target.get("type")
                or target.get("kind")
                or "UNKNOWN"
            )

            value = (
                target.get("value")
                or target.get("query")
                or target.get("name")
                or target.get("display_value")
                or "—"
            )

            return (
                f"{index}. [{target_type}] {value}"
            )

        target_type = getattr(
            target,
            "target_type",
            None,
        )

        value = getattr(
            target,
            "value",
            None,
        )

        if target_type is not None:

            normalized_type = (
                getattr(
                    target_type,
                    "value",
                    target_type,
                )
            )

            return (
                f"{index}. [{normalized_type}] "
                f"{value if value is not None else target}"
            )

        return (
            f"{index}. {target}"
        )

    @classmethod
    def _format_connectors(
        cls,
        connectors: list[Any],
    ) -> str:
        """
        Convert compatible connectors into readable text.
        """

        if not connectors:

            return (
                "No compatible connectors were found.\n\n"
                "Check that the form contains a supported target "
                "and that the required connectors are registered."
            )

        lines = [
            "Compatible OSINT connectors",
            "",
        ]

        for index, connector in enumerate(
            connectors,
            start=1,
        ):

            lines.append(
                f"{index}. {cls._connector_name(connector)}"
            )

        return "\n".join(
            lines
        )

    @staticmethod
    def _connector_name(
        connector: Any,
    ) -> str:
        """
        Return a readable connector name.
        """

        if isinstance(
            connector,
            str,
        ):

            return connector

        if isinstance(
            connector,
            dict,
        ):

            return str(
                connector.get("display_name")
                or connector.get("name")
                or connector.get("connector")
                or connector.get("id")
                or connector
            )

        for attribute in (
            "display_name",
            "name",
            "connector_name",
        ):

            value = getattr(
                connector,
                attribute,
                None,
            )

            if value:

                return str(
                    value
                )

        return str(
            connector
        )

    @classmethod
    def _format_investigation_response(
        cls,
        response: Any,
    ) -> str:
        """
        Format investigation results as rich HTML.

        Findings and discovery leads are displayed separately.

        Normalized Lead Engine data is preferred over raw
        connector-generated search URLs.
        """

        from html import escape

        if not isinstance(
            response,
            dict,
        ):
            return (
                "<pre>"
                + escape(
                    str(response)
                )
                + "</pre>"
            )

        # ======================================================
        # Helpers
        # ======================================================

        def safe(
            value: Any,
        ) -> str:

            if value is None:
                return ""

            return escape(
                str(value)
            )

        def safe_url(
            value: Any,
        ) -> str | None:

            text = str(
                value
                or ""
            ).strip()

            if not text.startswith(
                (
                    "https://",
                    "http://",
                )
            ):
                return None

            return escape(
                text,
                quote=True,
            )

        def link(
            url: Any,
            label: str,
        ) -> str:

            normalized = safe_url(
                url
            )

            if not normalized:
                return ""

            return (
                f'<a href="{normalized}">'
                f'{escape(label)}'
                f'</a>'
            )

        def platform_name(
            domain: Any,
        ) -> str:

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

        # ======================================================
        # Summary
        # ======================================================

        summary = response.get(
            "summary",
            {},
        )

        if not isinstance(
            summary,
            dict,
        ):
            summary = {}

        target_count = response.get(
            "target_count",
            0,
        )

        connector_runs = summary.get(
            "connector_runs",
            0,
        )

        total_findings = summary.get(
            "total_findings",
            0,
        )

        total_leads = summary.get(
            "total_leads",
            0,
        )

        total_items = summary.get(
            "total_items",
            (
                int(
                    total_findings
                    or 0
                )
                + int(
                    total_leads
                    or 0
                )
            ),
        )

        successful_runs = summary.get(
            "successful_runs",
            0,
        )

        failed_runs = summary.get(
            "failed_runs",
            0,
        )

        html: list[str] = []

        html.append(
            "<div>"
        )

        html.append(
            "<h2>Investigation summary</h2>"
        )

        html.append(
            "<p>"
            f"<b>Targets:</b> {safe(target_count)}"
            "&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Connectors:</b> {safe(connector_runs)}"
            "&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Findings:</b> {safe(total_findings)}"
            "&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Leads:</b> {safe(total_leads)}"
            "</p>"
        )

        html.append(
            "<p>"
            f"<b>Total items:</b> {safe(total_items)}"
            "&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Successful:</b> {safe(successful_runs)}"
            "&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Failed:</b> {safe(failed_runs)}"
            "</p>"
        )

        html.append(
            "<p>"
            "<i>"
            "Findings are extracted or confirmed information. "
            "Leads are search directions that still require "
            "verification."
            "</i>"
            "</p>"
        )

        target_results = response.get(
            "target_results",
            [],
        )

        if not isinstance(
            target_results,
            list,
        ):
            target_results = []

        # ======================================================
        # Targets
        # ======================================================

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
                "target",
                {},
            )

            if not isinstance(
                target,
                dict,
            ):
                target = {}

            html.append(
                "<hr>"
            )

            html.append(
                f"<h2>Target {target_index}</h2>"
            )

            html.append(
                "<p>"
                f"<b>Type:</b> "
                f"{safe(target.get('type'))}"
                "<br>"
                f"<b>Value:</b> "
                f"{safe(target.get('value'))}"
                "</p>"
            )

            connector_results = (
                target_result.get(
                    "results",
                    [],
                )
            )

            if not isinstance(
                connector_results,
                list,
            ):
                connector_results = []

            # ==================================================
            # Connector results
            # ==================================================

            for result in connector_results:

                if not isinstance(
                    result,
                    dict,
                ):
                    continue

                connector_name = result.get(
                    "connector",
                    "Unknown connector",
                )

                status = result.get(
                    "status",
                    "unknown",
                )

                finding_count = result.get(
                    "total_findings",
                    0,
                )

                lead_count = result.get(
                    "total_leads",
                    0,
                )

                html.append(
                    "<h3>"
                    f"{safe(connector_name)}"
                    "</h3>"
                )

                html.append(
                    "<p>"
                    f"<b>Status:</b> {safe(status)}"
                    "&nbsp;&nbsp;&nbsp;&nbsp;"
                    f"<b>Findings:</b> "
                    f"{safe(finding_count)}"
                    "&nbsp;&nbsp;&nbsp;&nbsp;"
                    f"<b>Leads:</b> "
                    f"{safe(lead_count)}"
                    "</p>"
                )

                error = result.get(
                    "error"
                )

                if error:

                    html.append(
                        "<p>"
                        "<b>Error:</b> "
                        f"{safe(error)}"
                        "</p>"
                    )

                items = result.get(
                    "findings",
                    [],
                )

                if not isinstance(
                    items,
                    list,
                ):
                    items = []

                findings: list[
                    dict[str, Any]
                ] = []

                leads: list[
                    dict[str, Any]
                ] = []

                for item in items:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    if (
                        item.get(
                            "kind"
                        )
                        == "lead"
                    ):
                        leads.append(
                            item
                        )
                    else:
                        findings.append(
                            item
                        )

                # ==============================================
                # Findings
                # ==============================================

                html.append(
                    "<h4>Findings</h4>"
                )

                if not findings:

                    html.append(
                        "<p>"
                        "No confirmed/extracted findings."
                        "</p>"
                    )

                else:

                    html.append(
                        "<ol>"
                    )

                    for finding in findings:

                        category = finding.get(
                            "category",
                            "finding",
                        )

                        value = finding.get(
                            "value",
                            "",
                        )

                        source = finding.get(
                            "source",
                            "",
                        )

                        url = finding.get(
                            "url"
                        )

                        confidence = finding.get(
                            "confidence"
                        )

                        reliability = finding.get(
                            "reliability"
                        )

                        html.append(
                            "<li>"
                        )

                        html.append(
                            "<b>"
                            f"{safe(category)}"
                            "</b>"
                        )

                        if value:

                            html.append(
                                "<br>"
                                f"Value: {safe(value)}"
                            )

                        if source:

                            html.append(
                                "<br>"
                                f"Source: {safe(source)}"
                            )

                        if confidence is not None:

                            html.append(
                                "<br>"
                                f"Confidence: "
                                f"{safe(confidence)}"
                            )

                        if reliability is not None:

                            html.append(
                                "<br>"
                                f"Reliability: "
                                f"{safe(reliability)}"
                            )

                        if url:

                            source_link = link(
                                url,
                                "Open source",
                            )

                            if source_link:

                                html.append(
                                    "<br>"
                                    + source_link
                                )

                        html.append(
                            "</li>"
                        )

                    html.append(
                        "</ol>"
                    )

                # ==============================================
                # Search leads
                # ==============================================

                html.append(
                    "<h4>Search leads</h4>"
                )

                if not leads:

                    html.append(
                        "<p>No search leads.</p>"
                    )

                    continue

                html.append(
                    "<p>"
                    "<i>"
                    "These are unverified search directions, "
                    "not confirmed accounts or matches."
                    "</i>"
                    "</p>"
                )

                for index, item in enumerate(
                    leads,
                    start=1,
                ):

                    normalized = item.get(
                        "lead"
                    )

                    if not isinstance(
                        normalized,
                        dict,
                    ):
                        normalized = {}

                    metadata = item.get(
                        "metadata",
                        {},
                    )

                    if not isinstance(
                        metadata,
                        dict,
                    ):
                        metadata = {}

                    domain = normalized.get(
                        "platform_domain"
                    )

                    display_platform = platform_name(
                        domain
                    )

                    category = (
                        normalized.get(
                            "category"
                        )
                        or metadata.get(
                            "category"
                        )
                        or item.get(
                            "category"
                        )
                        or "Search"
                    )

                    source = (
                        normalized.get(
                            "source"
                        )
                        or item.get(
                            "source"
                        )
                        or ""
                    )

                    search_urls = normalized.get(
                        "search_urls",
                        {},
                    )

                    if not isinstance(
                        search_urls,
                        dict,
                    ):
                        search_urls = {}

                    canonical_query = (
                        normalized.get(
                            "canonical_query"
                        )
                        or ""
                    )

                    variant_searches = (
                        normalized.get(
                            "variant_searches"
                        )
                        or ()
                    )

                    if not isinstance(
                        variant_searches,
                        (
                            list,
                            tuple,
                        ),
                    ):
                        variant_searches = ()

                    html.append(
                        "<div>"
                    )

                    html.append(
                        "<p>"
                        f"<b>{index}. "
                        f"{safe(display_platform)}</b>"
                        "<br>"
                        f"{safe(category)}"
                    )

                    if domain:

                        html.append(
                            " · "
                            f"{safe(domain)}"
                        )

                    html.append(
                        "<br>"
                        "<i>Unverified lead</i>"
                    )

                    if source:

                        html.append(
                            "<br>"
                            "Source: "
                            f"{safe(source)}"
                        )

                    html.append(
                        "</p>"
                    )

                    # ==========================================
                    # Lead Engine v1.1
                    # Per-query search table
                    # ==========================================

                    if variant_searches:

                        html.append(
                            '<table border="1" '
                            'cellspacing="0" '
                            'cellpadding="5" '
                            'width="100%">'
                        )

                        html.append(
                            "<tr>"
                            "<th align=\"left\">Variant</th>"
                            "<th align=\"left\">Query</th>"
                            "<th align=\"left\">Search</th>"
                            "</tr>"
                        )

                        rendered_variants = 0

                        for variant in (
                            variant_searches
                        ):

                            if not isinstance(
                                variant,
                                dict,
                            ):
                                continue

                            label = (
                                variant.get(
                                    "label"
                                )
                                or "Search"
                            )

                            query = (
                                variant.get(
                                    "query"
                                )
                                or ""
                            )

                            urls = (
                                variant.get(
                                    "search_urls"
                                )
                                or {}
                            )

                            if not isinstance(
                                urls,
                                dict,
                            ):
                                urls = {}

                            links: list[str] = []

                            google_url = urls.get(
                                "google"
                            )

                            bing_url = urls.get(
                                "bing"
                            )

                            duckduckgo_url = (
                                urls.get(
                                    "duckduckgo"
                                )
                            )

                            if google_url:

                                rendered = link(
                                    google_url,
                                    "Google",
                                )

                                if rendered:
                                    links.append(
                                        rendered
                                    )

                            if bing_url:

                                rendered = link(
                                    bing_url,
                                    "Bing",
                                )

                                if rendered:
                                    links.append(
                                        rendered
                                    )

                            if duckduckgo_url:

                                rendered = link(
                                    duckduckgo_url,
                                    "DuckDuckGo",
                                )

                                if rendered:
                                    links.append(
                                        rendered
                                    )

                            if not links:
                                links.append(
                                    "No search URLs"
                                )

                            html.append(
                                "<tr>"
                            )

                            html.append(
                                "<td>"
                                f"<b>{safe(label)}</b>"
                                "</td>"
                            )

                            html.append(
                                "<td>"
                                "<tt>"
                                f"{safe(query)}"
                                "</tt>"
                                "</td>"
                            )

                            html.append(
                                "<td>"
                                + " | ".join(
                                    links
                                )
                                + "</td>"
                            )

                            html.append(
                                "</tr>"
                            )

                            rendered_variants += 1

                        html.append(
                            "</table>"
                        )

                        if (
                            rendered_variants
                            == 0
                        ):

                            html.append(
                                "<p>"
                                "No usable query variants."
                                "</p>"
                            )

                    # ==========================================
                    # Backward-compatible fallback
                    # ==========================================

                    else:

                        engine_links: list[
                            str
                        ] = []

                        google_url = (
                            search_urls.get(
                                "google"
                            )
                        )

                        bing_url = (
                            search_urls.get(
                                "bing"
                            )
                        )

                        duckduckgo_url = (
                            search_urls.get(
                                "duckduckgo"
                            )
                        )

                        if google_url:

                            rendered = link(
                                google_url,
                                "Google",
                            )

                            if rendered:
                                engine_links.append(
                                    rendered
                                )

                        if bing_url:

                            rendered = link(
                                bing_url,
                                "Bing",
                            )

                            if rendered:
                                engine_links.append(
                                    rendered
                                )

                        if duckduckgo_url:

                            rendered = link(
                                duckduckgo_url,
                                "DuckDuckGo",
                            )

                            if rendered:
                                engine_links.append(
                                    rendered
                                )

                        if engine_links:

                            html.append(
                                "<p>"
                                "<b>Search:</b> "
                                + " | ".join(
                                    engine_links
                                )
                                + "</p>"
                            )

                        if canonical_query:

                            html.append(
                                "<p>"
                                "<b>Query:</b><br>"
                                "<tt>"
                                f"{safe(canonical_query)}"
                                "</tt>"
                                "</p>"
                            )

                    html.append(
                        "</div>"
                    )

                    html.append(
                        "<br>"
                    )

        if not target_results:

            html.append(
                "<p>No OSINT results.</p>"
            )

        html.append(
            "</div>"
        )

        return "".join(
            html
        )

    @classmethod
    def _format_section(
        cls,
        title: str,
        value: Any,
    ) -> list[str]:
        """
        Format one response section.
        """

        readable_title = (
            title
            .replace(
                "_",
                " ",
            )
            .strip()
            .title()
        )

        return [
            readable_title,
            cls._format_value(
                value,
                indentation=1,
            ),
            "",
        ]

    @classmethod
    def _format_value(
        cls,
        value: Any,
        indentation: int = 0,
    ) -> str:
        """
        Recursively format dictionaries and collections.
        """

        prefix = "    " * indentation

        if value is None:

            return f"{prefix}—"

        if isinstance(
            value,
            dict,
        ):

            if not value:

                return f"{prefix}{{}}"

            lines: list[str] = []

            for key, nested_value in (
                value.items()
            ):

                readable_key = (
                    str(
                        key
                    )
                    .replace(
                        "_",
                        " ",
                    )
                    .capitalize()
                )

                if isinstance(
                    nested_value,
                    (
                        dict,
                        list,
                        tuple,
                        set,
                    ),
                ):

                    lines.append(
                        f"{prefix}{readable_key}:"
                    )

                    lines.append(
                        cls._format_value(
                            nested_value,
                            indentation=(
                                indentation + 1
                            ),
                        )
                    )

                else:

                    lines.append(
                        (
                            f"{prefix}{readable_key}: "
                            f"{nested_value}"
                        )
                    )

            return "\n".join(
                lines
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            items = list(
                value
            )

            if not items:

                return f"{prefix}[]"

            lines = []

            for item in items:

                if isinstance(
                    item,
                    (
                        dict,
                        list,
                        tuple,
                        set,
                    ),
                ):

                    formatted_item = (
                        cls._format_value(
                            item,
                            indentation=(
                                indentation + 1
                            ),
                        )
                    )

                    lines.append(
                        f"{prefix}•"
                    )

                    lines.append(
                        formatted_item
                    )

                else:

                    lines.append(
                        f"{prefix}• {item}"
                    )

            return "\n".join(
                lines
            )

        return f"{prefix}{value}"

    # ==========================================================
    # State helpers
    # ==========================================================

    def _current_connector_count(
        self,
    ) -> int:
        """
        Return registered connector count from current view state.
        """

        state = (
            self.workspace_view
            .workspace_state()
        )

        count = state.get(
            "connector_count"
        )

        normalized_count = self._safe_int(
            count
        )

        if normalized_count is not None:

            return normalized_count

        connectors = (
            state.get("available_connectors")
            or state.get("connectors")
            or []
        )

        if isinstance(
            connectors,
            (
                list,
                tuple,
                set,
            ),
        ):

            return len(
                connectors
            )

        return 0

    @staticmethod
    def _has_meaningful_form_data(
        form_data: dict[str, Any],
    ) -> bool:
        """
        Determine whether the user entered meaningful target data.
        """

        ignored_keys = {
            "timeout",
            "use_cache",
            "save_raw_output",
            "include_metadata",
            "include_related",
        }

        for key, value in form_data.items():

            if key in ignored_keys:

                continue

            if value is None:

                continue

            if isinstance(
                value,
                str,
            ):

                if value.strip():

                    return True

                continue

            if isinstance(
                value,
                (
                    list,
                    tuple,
                    set,
                    dict,
                ),
            ):

                if value:

                    return True

                continue

            if value:

                return True

        return False