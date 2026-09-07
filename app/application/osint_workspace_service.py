"""
OSINT workspace application service.

Responsible for:

- preparing OSINT workspace data
- converting structured input into targets
- executing compatible OSINT connectors
- aggregating investigation results
- providing UI-ready result data

Does NOT:

- access database directly
- contain UI logic
- execute CLI tools directly
- create database entities
- call AI
"""

from __future__ import annotations

from app.osint.lead_normalizer import LeadNormalizer

from collections.abc import Iterable
from typing import Any

from app.osint.models import (
    ConnectorRequest,
    OsintInvestigationRequest,
    OsintTarget,
    OsintTargetType,
)

from app.osint.pipeline import (
    OsintPipeline,
)

from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)

from app.osint.target_builder import (
    OsintTargetBuilder,
)


class OsintWorkspaceService:
    """
    Application service for the OSINT workspace.

    Coordinates structured investigation requests,
    target creation and connector execution.
    """

    def __init__(
        self,
        pipeline: OsintPipeline,
        target_builder: OsintTargetBuilder,
    ) -> None:

        self.pipeline = pipeline

        self.target_builder = target_builder

    # ==========================================================
    # Workspace
    # ==========================================================

    def get_workspace_state(
        self,
    ) -> dict[str, Any]:
        """
        Return initial OSINT workspace state.
        """

        connector_names = (
            self.pipeline
            .available_connectors()
        )

        return {
            "connectors": connector_names,
            "connector_count": len(
                connector_names
            ),
            "target_types": [
                target_type.value
                for target_type in OsintTargetType
            ],
        }

    # ==========================================================
    # Targets
    # ==========================================================

    def build_targets(
        self,
        request: OsintInvestigationRequest,
    ) -> list[dict[str, Any]]:
        """
        Build and serialize investigation targets.
        """

        targets = self.target_builder.build(
            request
        )

        return [
            self._serialize_target(
                target
            )
            for target in targets
        ]

    def get_compatible_connectors(
        self,
        request: OsintInvestigationRequest,
    ) -> list[dict[str, Any]]:
        """
        Return compatible connectors for every target.
        """

        targets = self.target_builder.build(
            request
        )

        result: list[dict[str, Any]] = []

        for target in targets:

            connectors = (
                self.pipeline
                .manager
                .registry
                .supported(
                    target.target_type
                )
            )

            result.append(
                {
                    "target": (
                        self._serialize_target(
                            target
                        )
                    ),
                    "connectors": [
                        connector.name
                        for connector in connectors
                    ],
                    "connector_count": len(
                        connectors
                    ),
                }
            )

        return result

    # ==========================================================
    # Investigation execution
    # ==========================================================

    def run_investigation(
        self,
        request: OsintInvestigationRequest,
        selected_connectors: Iterable[str] | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> dict[str, Any]:
        """
        Run an OSINT investigation for all built targets.

        When selected_connectors is None, every compatible
        connector is executed.

        When selected_connectors contains names, only matching
        compatible connectors are executed.
        """

        targets = self.target_builder.build(
            request
        )

        selected_connector_names = (
            self._normalize_connector_names(
                selected_connectors
            )
        )

        target_results: list[
            dict[str, Any]
        ] = []

        all_results: list[
            OsintResult
        ] = []

        for target in targets:

            connector_request = ConnectorRequest(
                target=target,
                timeout=timeout,
                use_cache=use_cache,
                save_raw_output=save_raw_output,
                include_metadata=include_metadata,
                include_related=include_related,
            )

            results = self._run_target(
                connector_request=connector_request,
                selected_connector_names=(
                    selected_connector_names
                ),
            )

            all_results.extend(
                results
            )

            target_results.append(
                {
                    "target": (
                        self._serialize_target(
                            target
                        )
                    ),
                    "results": [
                        self._serialize_result(
                            result
                        )
                        for result in results
                    ],
                    "summary": (
                        self._build_summary(
                            results
                        )
                    ),
                }
            )

        return {
            "case_id": request.case_id,
            "title": request.title,
            "description": request.description,

            "targets": [
                self._serialize_target(
                    target
                )
                for target in targets
            ],

            "target_count": len(
                targets
            ),

            "selected_connectors": (
                sorted(
                    selected_connector_names
                )
                if selected_connector_names
                is not None
                else None
            ),

            "target_results": target_results,

            "summary": self._build_summary(
                all_results
            ),
        }

    def run_target(
        self,
        target: OsintTarget,
        selected_connectors: Iterable[str] | None = None,
        timeout: int = 300,
        use_cache: bool = True,
        save_raw_output: bool = False,
        include_metadata: bool = True,
        include_related: bool = True,
    ) -> dict[str, Any]:
        """
        Run connectors for one already-built target.
        """

        connector_request = ConnectorRequest(
            target=target,
            timeout=timeout,
            use_cache=use_cache,
            save_raw_output=save_raw_output,
            include_metadata=include_metadata,
            include_related=include_related,
        )

        selected_connector_names = (
            self._normalize_connector_names(
                selected_connectors
            )
        )

        results = self._run_target(
            connector_request=connector_request,
            selected_connector_names=(
                selected_connector_names
            ),
        )

        return {
            "target": self._serialize_target(
                target
            ),
            "results": [
                self._serialize_result(
                    result
                )
                for result in results
            ],
            "summary": self._build_summary(
                results
            ),
        }

    # ==========================================================
    # Connector execution
    # ==========================================================

    def _run_target(
        self,
        connector_request: ConnectorRequest,
        selected_connector_names: set[str] | None,
    ) -> list[OsintResult]:
        """
        Execute compatible connectors for one target.
        """

        if selected_connector_names is None:

            return self.pipeline.run(
                connector_request
            )

        compatible_connectors = (
            self.pipeline
            .manager
            .registry
            .supported(
                connector_request
                .target
                .target_type
            )
        )

        results: list[
            OsintResult
        ] = []

        for connector in compatible_connectors:

            normalized_name = (
                connector.name
                .strip()
                .lower()
            )

            if (
                normalized_name
                not in selected_connector_names
            ):
                continue

            result = (
                self.pipeline
                .run_connector(
                    connector_name=connector.name,
                    request=connector_request,
                )
            )

            if result is not None:

                results.append(
                    result
                )

        return results

    # ==========================================================
    # Serialization
    # ==========================================================

    def _serialize_target(
        self,
        target: OsintTarget,
    ) -> dict[str, Any]:
        """
        Convert an OSINT target into UI-ready data.
        """

        return {
            "type": target.target_type.value,
            "value": target.value,
            "label": target.label,
            "description": target.description,
            "case_id": target.case_id,
        }

    @staticmethod
    def _is_lead_finding(
        finding: OsintFinding,
    ) -> bool:
        """
        Return whether a finding is a discovery lead rather
        than extracted or confirmed information.

        Connectors can classify a result as a lead by setting:

            metadata["lead_only"] = True

        Missing metadata keeps existing connectors backward
        compatible and classifies their results as findings.
        """

        metadata = getattr(
            finding,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return False

        return bool(
            metadata.get(
                "lead_only",
                False,
            )
        )

    def _serialize_result(
        self,
        result: OsintResult,
    ) -> dict[str, Any]:
        """
        Convert an OSINT result into UI-ready data.

        Findings and discovery leads are counted separately.
        """

        lead_count = sum(
            1
            for finding in result.findings
            if self._is_lead_finding(
                finding
            )
        )

        finding_count = (
            result.total_findings
            - lead_count
        )

        return {
            "connector": result.connector,
            "status": result.status.value,
            "success": result.success,

            # Semantic counters.
            "total_items": result.total_findings,
            "total_findings": finding_count,
            "total_leads": lead_count,

            "findings": [
                self._serialize_finding(
                    finding
                )
                for finding in result.findings
            ],

            "raw_data": result.raw_data,
            "execution_time": (
                result.execution_time
            ),
            "error": result.error,
            "metadata": dict(
                result.metadata
            ),
        }

    def _serialize_finding(
        self,
        finding: OsintFinding,
    ) -> dict[str, Any]:
        """
        Convert a finding into UI-ready data.

        Discovery leads are enriched by LeadNormalizer so the
        frontend receives clean platform/query/search-engine data.
        """

        is_lead = self._is_lead_finding(
            finding
        )

        serialized: dict[str, Any] = {
            "kind": (
                "lead"
                if is_lead
                else "finding"
            ),
            "lead_only": is_lead,
            "category": finding.category,
            "value": finding.value,
            "confidence": finding.confidence,
            "source": finding.source,
            "url": finding.url,
            "reliability": finding.reliability,
            "metadata": dict(
                finding.metadata
            ),
        }

        if is_lead:

            try:

                normalized_lead = (
                    LeadNormalizer
                    .normalize(
                        serialized
                    )
                )

                serialized[
                    "lead"
                ] = (
                    normalized_lead
                    .to_dict()
                )

            except Exception as exc:

                # A malformed lead must never break the
                # connector result or the entire investigation.
                serialized[
                    "lead"
                ] = None

                serialized[
                    "lead_normalization_error"
                ] = str(
                    exc
                )

        else:

            serialized[
                "lead"
            ] = None

        return serialized

    # ==========================================================
    # Summary
    # ==========================================================

    def _build_summary(
        self,
        results: Iterable[OsintResult],
    ) -> dict[str, Any]:
        """
        Build connector execution summary.

        total_findings contains extracted/confirmed findings.
        total_leads contains discovery/search leads.
        total_items is the complete raw item count.
        """

        result_list = list(
            results
        )

        status_counts = {
            status.value: 0
            for status in ResultStatus
        }

        total_findings = 0
        total_leads = 0
        total_items = 0
        total_execution_time = 0.0

        for result in result_list:

            status_counts[
                result.status.value
            ] += 1

            total_execution_time += (
                result.execution_time
            )

            for finding in result.findings:

                total_items += 1

                if self._is_lead_finding(
                    finding
                ):
                    total_leads += 1
                else:
                    total_findings += 1

        successful_results = (
            status_counts[
                ResultStatus.SUCCESS.value
            ]
            + status_counts[
                ResultStatus.PARTIAL.value
            ]
        )

        failed_results = (
            status_counts[
                ResultStatus.FAILED.value
            ]
        )

        return {
            "connector_runs": len(
                result_list
            ),
            "successful_runs": (
                successful_results
            ),
            "failed_runs": failed_results,

            "total_findings": (
                total_findings
            ),
            "total_leads": (
                total_leads
            ),
            "total_items": (
                total_items
            ),

            "execution_time": (
                total_execution_time
            ),
            "statuses": status_counts,
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    def _normalize_connector_names(
        self,
        connector_names: Iterable[str] | None,
    ) -> set[str] | None:
        """
        Normalize selected connector names.
        """

        if connector_names is None:
            return None

        normalized_names: set[str] = set()

        for name in connector_names:

            normalized_name = (
                str(
                    name
                )
                .strip()
                .lower()
            )

            if normalized_name:

                normalized_names.add(
                    normalized_name
                )

        return normalized_names