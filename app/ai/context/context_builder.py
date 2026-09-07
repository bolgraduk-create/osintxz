"""
AI context builder.

Responsible for:

- preparing investigation data for AI prompts
- building context for one selected message
- building context for selected message groups
- building context for the complete investigation
- limiting and truncating large datasets
- converting values into JSON-safe structures
- exposing context statistics

Does NOT:

- access database
- call AI providers
- render prompts
- execute investigation business logic
"""


from __future__ import annotations

from copy import deepcopy
from datetime import UTC
from datetime import date
from datetime import datetime
import json
from typing import Any
from uuid import UUID

from app.ai.context.message_context_selector import (
    MessageContextSelector,
)


class ContextBuilder:
    """
    Builds safe, bounded and serializable AI context.

    The builder expects workspace data in the format returned by
    CaseWorkspaceService.get_workspace().
    """

    DEFAULT_MAX_MESSAGES = 100

    DEFAULT_RELATED_MESSAGE_LIMIT = 20

    DEFAULT_MAX_EVIDENCE = 50

    DEFAULT_MAX_ENTITIES = 100

    DEFAULT_MAX_RELATIONSHIPS = 100

    DEFAULT_MAX_TIMELINE_EVENTS = 100

    DEFAULT_MAX_REPORTS = 20

    DEFAULT_TEXT_LIMIT = 4000

    DEFAULT_MESSAGE_TEXT_LIMIT = 2000

    DEFAULT_REPORT_CONTENT_LIMIT = 6000

    def __init__(
        self,
        *,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        related_message_limit: int = DEFAULT_RELATED_MESSAGE_LIMIT,
        max_evidence: int = DEFAULT_MAX_EVIDENCE,
        max_entities: int = DEFAULT_MAX_ENTITIES,
        max_relationships: int = DEFAULT_MAX_RELATIONSHIPS,
        max_timeline_events: int = DEFAULT_MAX_TIMELINE_EVENTS,
        max_reports: int = DEFAULT_MAX_REPORTS,
        text_limit: int = DEFAULT_TEXT_LIMIT,
        message_text_limit: int = DEFAULT_MESSAGE_TEXT_LIMIT,
        report_content_limit: int = DEFAULT_REPORT_CONTENT_LIMIT,
    ) -> None:

        self.max_messages = self._normalize_positive_limit(
            max_messages,
            field_name="max_messages",
        )

        self.related_message_limit = self._normalize_positive_limit(
            related_message_limit,
            field_name="related_message_limit",
        )

        self.max_evidence = self._normalize_positive_limit(
            max_evidence,
            field_name="max_evidence",
        )

        self.max_entities = self._normalize_positive_limit(
            max_entities,
            field_name="max_entities",
        )

        self.max_relationships = self._normalize_positive_limit(
            max_relationships,
            field_name="max_relationships",
        )

        self.max_timeline_events = self._normalize_positive_limit(
            max_timeline_events,
            field_name="max_timeline_events",
        )

        self.max_reports = self._normalize_positive_limit(
            max_reports,
            field_name="max_reports",
        )

        self.text_limit = self._normalize_positive_limit(
            text_limit,
            field_name="text_limit",
        )

        self.message_text_limit = self._normalize_positive_limit(
            message_text_limit,
            field_name="message_text_limit",
        )

        self.report_content_limit = self._normalize_positive_limit(
            report_content_limit,
            field_name="report_content_limit",
        )

        self.context: dict[str, Any] = {}

        self.reset()

        self.message_context_selector = (
            MessageContextSelector(
                previous_limit=10,
                next_limit=10,
            )
        )

    # ==========================================================
    # State
    # ==========================================================

    def reset(
        self,
    ) -> None:
        """
        Reset current context.
        """

        self.context = self._empty_context(
            context_type="empty"
        )

    def get_context(
        self,
    ) -> dict[str, Any]:
        """
        Return a defensive copy of the current context.
        """

        return deepcopy(
            self.context
        )

    # ==========================================================
    # Investigation context
    # ==========================================================

    def build_investigation_context(
        self,
        workspace: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Build bounded context for the complete investigation.
        """

        normalized_workspace = self._normalize_workspace(
            workspace
        )

        messages = self._prepare_messages(
            self._get_list(
                normalized_workspace,
                "messages",
            ),
            limit=self.max_messages,
        )

        evidence = self._prepare_evidence(
            self._get_list(
                normalized_workspace,
                "evidence",
            ),
            limit=self.max_evidence,
        )

        entities = self._prepare_entities(
            self._get_list(
                normalized_workspace,
                "entities",
            ),
            limit=self.max_entities,
        )

        relationships = self._prepare_relationships(
            self._get_list(
                normalized_workspace,
                "relationships",
            ),
            limit=self.max_relationships,
        )

        timeline = self._prepare_timeline(
            self._get_list(
                normalized_workspace,
                "timeline",
            ),
            limit=self.max_timeline_events,
        )

        reports = self._prepare_reports(
            self._get_list(
                normalized_workspace,
                "reports",
            ),
            limit=self.max_reports,
        )

        self.context = {
            "context_type": "investigation",
            "case": self._prepare_case(
                normalized_workspace.get(
                    "case"
                )
            ),
            "statistics": self._prepare_statistics(
                normalized_workspace.get(
                    "statistics"
                )
            ),
            "messages": messages,
            "evidence": evidence,
            "entities": entities,
            "relationships": relationships,
            "timeline": timeline,
            "reports": reports,
            "graph": self._prepare_graph(
                normalized_workspace.get(
                    "graph"
                )
            ),
            "metadata": self._build_metadata(
                normalized_workspace=normalized_workspace,
                included_counts={
                    "messages": len(
                        messages
                    ),
                    "evidence": len(
                        evidence
                    ),
                    "entities": len(
                        entities
                    ),
                    "relationships": len(
                        relationships
                    ),
                    "timeline": len(
                        timeline
                    ),
                    "reports": len(
                        reports
                    ),
                },
            ),
        }

        return self.get_context()

    # ==========================================================
    # Message context
    # ==========================================================

    def build_message_context(
        self,
        workspace: dict[str, Any] | None,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build context for one selected message.

        Includes:

        - selected message
        - chronological messages before it
        - chronological messages after it
        - related entities
        - related evidence
        - related timeline events
        - related relationships
        - reports
        - workspace statistics
        """

        if not isinstance(
            message,
            dict,
        ):

            raise TypeError(
                "message must be a dictionary."
            )

        normalized_workspace = self._normalize_workspace(
            workspace
        )

        workspace_messages = self._get_list(
            normalized_workspace,
            "messages",
        )

        chronological_context = (
            self.message_context_selector
            .select(
                messages=workspace_messages,
                selected_message=message,
            )
        )

        selected_message = self._prepare_message(
            chronological_context.get(
                "selected_message",
                message,
            )
        )

        previous_messages = self._prepare_messages(
            chronological_context.get(
                "previous_messages",
                [],
            ),
            limit=self.max_messages,
        )

        next_messages = self._prepare_messages(
            chronological_context.get(
                "next_messages",
                [],
            ),
            limit=self.max_messages,
        )

        selected_sender = self._normalized_compare_text(
            selected_message.get(
                "sender"
            )
        )

        selected_receiver = self._normalized_compare_text(
            selected_message.get(
                "receiver"
            )
        )

        selected_chat = self._normalized_compare_text(
            selected_message.get(
                "chat_name"
            )
        )

        participant_values = {
            selected_sender,
            selected_receiver,
            selected_chat,
        }

        entities = self._prepare_entities(
            self._filter_entities_for_message(
                entities=self._get_list(
                    normalized_workspace,
                    "entities",
                ),
                values=participant_values,
            ),
            limit=self.max_entities,
        )

        evidence = self._prepare_evidence(
            self._filter_evidence_for_message(
                evidence=self._get_list(
                    normalized_workspace,
                    "evidence",
                ),
                selected_message=selected_message,
            ),
            limit=self.max_evidence,
        )

        timeline = self._prepare_timeline(
            self._filter_timeline_for_message(
                timeline=self._get_list(
                    normalized_workspace,
                    "timeline",
                ),
                selected_message=selected_message,
            ),
            limit=self.max_timeline_events,
        )

        relationships = (
            self._prepare_relationships(
                self._filter_relationships_for_entities(
                    relationships=self._get_list(
                        normalized_workspace,
                        "relationships",
                    ),
                    entities=entities,
                ),
                limit=self.max_relationships,
            )
        )

        reports = self._prepare_reports(
            self._get_list(
                normalized_workspace,
                "reports",
            ),
            limit=self.max_reports,
        )

        statistics = self._prepare_statistics(
            normalized_workspace.get(
                "statistics"
            )
        )

        self.context = {
            "context_type": "message",
            "case": self._prepare_case(
                normalized_workspace.get(
                    "case"
                )
            ),
            "statistics": statistics,
            "previous_messages": previous_messages,
            "selected_message": selected_message,
            "next_messages": next_messages,
            "related_entities": entities,
            "related_evidence": evidence,
            "related_relationships": relationships,
            "related_timeline": timeline,
            "reports": reports,
            "metadata": self._build_metadata(
                normalized_workspace=normalized_workspace,
                included_counts={
                    "selected_messages": 1,
                    "previous_messages": len(
                        previous_messages
                    ),
                    "next_messages": len(
                        next_messages
                    ),
                    "entities": len(
                        entities
                    ),
                    "evidence": len(
                        evidence
                    ),
                    "relationships": len(
                        relationships
                    ),
                    "timeline": len(
                        timeline
                    ),
                    "reports": len(
                        reports
                    ),
                },
            ),
        }

        return self.get_context()

    def _filter_relationships_for_entities(
        self,
        *,
        relationships: list[Any],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Find relationships connected to the supplied entities.
        """

        entity_ids = {
            self._normalized_compare_text(
                entity.get(
                    "id"
                )
            )
            for entity in entities
            if isinstance(
                entity,
                dict,
            )
            and entity.get(
                "id"
            )
        }

        if not entity_ids:

            return []

        result: list[
            dict[str, Any]
        ] = []

        for relationship in relationships:

            if not isinstance(
                relationship,
                dict,
            ):

                continue

            source_id = self._normalized_compare_text(
                relationship.get(
                    "source"
                )
                or relationship.get(
                    "source_entity_id"
                )
            )

            target_id = self._normalized_compare_text(
                relationship.get(
                    "target"
                )
                or relationship.get(
                    "target_entity_id"
                )
            )

            if (
                source_id in entity_ids
                or target_id in entity_ids
            ):

                result.append(
                    relationship
                )

        return result

    # ==========================================================
    # Message collection context
    # ==========================================================

    def build_message_collection_context(
        self,
        workspace: dict[str, Any] | None,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Build AI context for a selected message collection.
        """

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        normalized_workspace = self._normalize_workspace(
            workspace
        )

        selected_messages = self._prepare_messages(
            [
                message
                for message in messages
                if isinstance(
                    message,
                    dict,
                )
            ],
            limit=self.max_messages,
        )

        if not selected_messages:

            raise ValueError(
                "No valid selected messages were provided."
            )

        participant_values: set[str] = set()

        for message in selected_messages:

            for field_name in (
                "sender",
                "receiver",
                "chat_name",
            ):

                normalized_value = (
                    self._normalized_compare_text(
                        message.get(
                            field_name
                        )
                    )
                )

                if normalized_value:

                    participant_values.add(
                        normalized_value
                    )

        entities = self._prepare_entities(
            self._filter_entities_for_message(
                entities=self._get_list(
                    normalized_workspace,
                    "entities",
                ),
                values=participant_values,
            ),
            limit=self.max_entities,
        )

        self.context = {
            "context_type": "message_collection",
            "case": self._prepare_case(
                normalized_workspace.get(
                    "case"
                )
            ),
            "messages": selected_messages,
            "participants": self._build_participant_summary(
                selected_messages
            ),
            "related_entities": entities,
            "metadata": self._build_metadata(
                normalized_workspace=normalized_workspace,
                included_counts={
                    "messages": len(
                        selected_messages
                    ),
                    "entities": len(
                        entities
                    ),
                },
            ),
        }

        return self.get_context()

    # ==========================================================
    # Legacy incremental API
    # ==========================================================

    def build_case_context(
        self,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build a minimal case context.

        Preserved for compatibility with the earlier API.
        """

        self.context = self._empty_context(
            context_type="case"
        )

        self.context["case"] = self._prepare_case(
            case
        )

        return self.get_context()

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """
        Add documents to the current context.
        """

        self._extend_context_list(
            key="documents",
            values=documents,
            limit=self.max_evidence,
        )

    def add_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Add messages to the current context.
        """

        prepared_messages = self._prepare_messages(
            messages,
            limit=self.max_messages,
        )

        self.context.setdefault(
            "messages",
            [],
        ).extend(
            prepared_messages
        )

        self.context["messages"] = (
            self.context["messages"][
                :self.max_messages
            ]
        )

    def add_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> None:
        """
        Add entities to the current context.
        """

        prepared_entities = self._prepare_entities(
            entities,
            limit=self.max_entities,
        )

        self.context.setdefault(
            "entities",
            [],
        ).extend(
            prepared_entities
        )

        self.context["entities"] = (
            self.context["entities"][
                :self.max_entities
            ]
        )

    def add_relationships(
        self,
        relationships: list[dict[str, Any]],
    ) -> None:
        """
        Add relationships to the current context.
        """

        prepared_relationships = (
            self._prepare_relationships(
                relationships,
                limit=self.max_relationships,
            )
        )

        self.context.setdefault(
            "relationships",
            [],
        ).extend(
            prepared_relationships
        )

        self.context["relationships"] = (
            self.context["relationships"][
                :self.max_relationships
            ]
        )

    def add_analysis_results(
        self,
        results: list[dict[str, Any]],
    ) -> None:
        """
        Add previous AI results to the current context.
        """

        self._extend_context_list(
            key="analysis_results",
            values=results,
            limit=self.max_reports,
        )

    # ==========================================================
    # Prompt-ready output
    # ==========================================================

    def to_prompt_text(
        self,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Convert context into readable JSON text for prompts.
        """

        target_context = (
            context
            if isinstance(
                context,
                dict,
            )
            else self.context
        )

        return json.dumps(
            self._make_json_safe(
                target_context
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )

    def estimate_character_count(
        self,
        context: dict[str, Any] | None = None,
    ) -> int:
        """
        Return approximate serialized character count.
        """

        return len(
            self.to_prompt_text(
                context
            )
        )

    def estimate_token_count(
        self,
        context: dict[str, Any] | None = None,
    ) -> int:
        """
        Return a rough token estimate.

        This uses four characters per token as a conservative,
        provider-independent approximation.
        """

        character_count = (
            self.estimate_character_count(
                context
            )
        )

        return max(
            1,
            (
                character_count
                + 3
            )
            // 4,
        )

    # ==========================================================
    # Summary and metadata
    # ==========================================================

    def summarize_context(
        self,
    ) -> dict[str, Any]:
        """
        Return counts for list-based context sections.
        """

        summary: dict[str, Any] = {
            "context_type": self.context.get(
                "context_type",
                "unknown",
            )
        }

        for key, value in self.context.items():

            if isinstance(
                value,
                list,
            ):

                summary[key] = len(
                    value
                )

        summary[
            "estimated_characters"
        ] = self.estimate_character_count()

        summary[
            "estimated_tokens"
        ] = self.estimate_token_count()

        return summary

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return builder configuration and current context metadata.
        """

        return {
            "type": "investigation_context",
            "context_type": self.context.get(
                "context_type",
                "unknown",
            ),
            "sections": list(
                self.context.keys()
            ),
            "limits": {
                "messages": self.max_messages,
                "related_messages": (
                    self.related_message_limit
                ),
                "evidence": self.max_evidence,
                "entities": self.max_entities,
                "relationships": (
                    self.max_relationships
                ),
                "timeline": (
                    self.max_timeline_events
                ),
                "reports": self.max_reports,
                "text": self.text_limit,
                "message_text": (
                    self.message_text_limit
                ),
                "report_content": (
                    self.report_content_limit
                ),
            },
            "summary": self.summarize_context(),
        }

    # ==========================================================
    # Preparation
    # ==========================================================

    def _prepare_case(
        self,
        value: Any,
    ) -> dict[str, Any]:
        """
        Prepare case information.
        """

        case = (
            value
            if isinstance(
                value,
                dict,
            )
            else {}
        )

        return {
            "id": self._normalize_scalar(
                case.get(
                    "id"
                )
            ),
            "title": self._truncate_text(
                case.get(
                    "title"
                )
                or case.get(
                    "name"
                ),
                self.text_limit,
            ),
            "description": self._truncate_text(
                case.get(
                    "description"
                ),
                self.text_limit,
            ),
        }

    def _prepare_statistics(
        self,
        value: Any,
    ) -> dict[str, int]:
        """
        Prepare workspace statistics.
        """

        statistics = (
            value
            if isinstance(
                value,
                dict,
            )
            else {}
        )

        result: dict[str, int] = {}

        for key in (
            "messages",
            "evidence",
            "entities",
            "relationships",
            "reports",
            "timeline",
        ):

            raw_value = statistics.get(
                key,
                0,
            )

            try:

                result[key] = int(
                    raw_value
                    or 0
                )

            except (
                TypeError,
                ValueError,
            ):

                result[key] = 0

        return result

    def _prepare_messages(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare, sort and limit messages.
        """

        prepared = [
            self._prepare_message(
                value
            )
            for value in values
            if isinstance(
                value,
                dict,
            )
        ]

        prepared.sort(
            key=lambda message: (
                self._message_sort_key(
                    message
                )
            )
        )

        if len(
            prepared
        ) <= limit:

            return prepared

        return prepared[
            -limit:
        ]

    def _prepare_message(
        self,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Prepare one message.
        """

        return {
            "id": self._normalize_scalar(
                value.get(
                    "id"
                )
            ),
            "source_id": self._normalize_scalar(
                value.get(
                    "source_id"
                )
            ),
            "evidence_id": self._normalize_scalar(
                value.get(
                    "evidence_id"
                )
            ),
            "external_id": self._normalize_scalar(
                value.get(
                    "external_id"
                )
            ),
            "sent_at": self._normalize_scalar(
                value.get(
                    "sent_at"
                )
            ),
            "sender": self._truncate_text(
                value.get(
                    "sender"
                ),
                512,
            ),
            "receiver": self._truncate_text(
                value.get(
                    "receiver"
                ),
                512,
            ),
            "chat_name": self._truncate_text(
                value.get(
                    "chat_name"
                ),
                512,
            ),
            "text": self._truncate_text(
                value.get(
                    "text"
                ),
                self.message_text_limit,
            ),
            "reply_to_id": self._normalize_scalar(
                value.get(
                    "reply_to_id"
                )
            ),
            "metadata": self._normalize_metadata(
                value.get(
                    "metadata_json"
                )
            ),
        }

    def _prepare_evidence(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare evidence objects.
        """

        prepared: list[
            dict[str, Any]
        ] = []

        for value in values:

            if not isinstance(
                value,
                dict,
            ):

                continue

            prepared.append(
                {
                    "id": self._normalize_scalar(
                        value.get(
                            "id"
                        )
                    ),
                    "title": self._truncate_text(
                        value.get(
                            "title"
                        ),
                        512,
                    ),
                    "type": self._normalize_scalar(
                        value.get(
                            "type"
                        )
                    ),
                    "value": self._truncate_text(
                        value.get(
                            "value"
                        ),
                        self.text_limit,
                    ),
                    "file_path": self._truncate_text(
                        value.get(
                            "file_path"
                        ),
                        1024,
                    ),
                    "mime_type": self._truncate_text(
                        value.get(
                            "mime_type"
                        ),
                        256,
                    ),
                }
            )

        return prepared[
            :limit
        ]

    def _prepare_entities(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare entity objects.
        """

        prepared: list[
            dict[str, Any]
        ] = []

        for value in values:

            if not isinstance(
                value,
                dict,
            ):

                continue

            prepared.append(
                {
                    "id": self._normalize_scalar(
                        value.get(
                            "id"
                        )
                    ),
                    "type": self._normalize_scalar(
                        value.get(
                            "type"
                        )
                    ),
                    "value": self._truncate_text(
                        value.get(
                            "value"
                        ),
                        512,
                    ),
                    "normalized_value": self._truncate_text(
                        value.get(
                            "normalized_value"
                        ),
                        512,
                    ),
                    "confidence": self._normalize_float(
                        value.get(
                            "confidence"
                        )
                    ),
                }
            )

        return prepared[
            :limit
        ]

    def _prepare_relationships(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare relationship objects.
        """

        prepared: list[
            dict[str, Any]
        ] = []

        for value in values:

            if not isinstance(
                value,
                dict,
            ):

                continue

            prepared.append(
                {
                    "id": self._normalize_scalar(
                        value.get(
                            "id"
                        )
                    ),
                    "type": self._normalize_scalar(
                        value.get(
                            "type"
                        )
                    ),
                    "source": self._normalize_scalar(
                        value.get(
                            "source"
                        )
                    ),
                    "target": self._normalize_scalar(
                        value.get(
                            "target"
                        )
                    ),
                    "confidence": self._normalize_float(
                        value.get(
                            "confidence"
                        )
                    ),
                }
            )

        return prepared[
            :limit
        ]

    def _prepare_timeline(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare and sort timeline events.
        """

        prepared: list[
            dict[str, Any]
        ] = []

        for value in values:

            if not isinstance(
                value,
                dict,
            ):

                continue

            prepared.append(
                {
                    "id": self._normalize_scalar(
                        value.get(
                            "id"
                        )
                    ),
                    "title": self._truncate_text(
                        value.get(
                            "title"
                        ),
                        512,
                    ),
                    "date": self._normalize_scalar(
                        value.get(
                            "date"
                        )
                        or value.get(
                            "event_time"
                        )
                    ),
                    "type": self._normalize_scalar(
                        value.get(
                            "type"
                        )
                    ),
                    "description": self._truncate_text(
                        value.get(
                            "description"
                        ),
                        self.text_limit,
                    ),
                }
            )

        prepared.sort(
            key=lambda event: str(
                event.get(
                    "date"
                )
                or ""
            )
        )

        return prepared[
            :limit
        ]

    def _prepare_reports(
        self,
        values: list[Any],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Prepare report objects.
        """

        prepared: list[
            dict[str, Any]
        ] = []

        for value in values:

            if not isinstance(
                value,
                dict,
            ):

                continue

            prepared.append(
                {
                    "id": self._normalize_scalar(
                        value.get(
                            "id"
                        )
                    ),
                    "title": self._truncate_text(
                        value.get(
                            "title"
                        ),
                        512,
                    ),
                    "type": self._normalize_scalar(
                        value.get(
                            "type"
                        )
                    ),
                    "content": self._truncate_text(
                        value.get(
                            "content"
                        ),
                        self.report_content_limit,
                    ),
                }
            )

        return prepared[
            :limit
        ]

    def _prepare_graph(
        self,
        value: Any,
    ) -> dict[str, Any]:
        """
        Prepare a compact graph summary.
        """

        graph = (
            value
            if isinstance(
                value,
                dict,
            )
            else {}
        )

        nodes = graph.get(
            "nodes",
            [],
        )

        edges = graph.get(
            "edges",
            [],
        )

        statistics = graph.get(
            "statistics",
            {},
        )

        return {
            "node_count": (
                len(
                    nodes
                )
                if isinstance(
                    nodes,
                    list,
                )
                else 0
            ),
            "edge_count": (
                len(
                    edges
                )
                if isinstance(
                    edges,
                    list,
                )
                else 0
            ),
            "statistics": self._make_json_safe(
                statistics
                if isinstance(
                    statistics,
                    dict,
                )
                else {}
            ),
        }

    # ==========================================================
    # Related data
    # ==========================================================

    def _find_related_messages(
        self,
        *,
        messages: list[Any],
        selected_message: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Find contextually related messages.
        """

        selected_id = self._normalized_compare_text(
            selected_message.get(
                "id"
            )
        )

        selected_sender = self._normalized_compare_text(
            selected_message.get(
                "sender"
            )
        )

        selected_receiver = self._normalized_compare_text(
            selected_message.get(
                "receiver"
            )
        )

        selected_chat = self._normalized_compare_text(
            selected_message.get(
                "chat_name"
            )
        )

        related: list[
            dict[str, Any]
        ] = []

        for raw_message in messages:

            if not isinstance(
                raw_message,
                dict,
            ):

                continue

            prepared_message = self._prepare_message(
                raw_message
            )

            message_id = self._normalized_compare_text(
                prepared_message.get(
                    "id"
                )
            )

            if (
                selected_id
                and message_id == selected_id
            ):

                continue

            sender = self._normalized_compare_text(
                prepared_message.get(
                    "sender"
                )
            )

            receiver = self._normalized_compare_text(
                prepared_message.get(
                    "receiver"
                )
            )

            chat = self._normalized_compare_text(
                prepared_message.get(
                    "chat_name"
                )
            )

            same_chat = bool(
                selected_chat
                and chat == selected_chat
            )

            participant_overlap = bool(
                {
                    selected_sender,
                    selected_receiver,
                }
                & {
                    sender,
                    receiver,
                }
                - {
                    ""
                }
            )

            if (
                same_chat
                or participant_overlap
            ):

                related.append(
                    prepared_message
                )

        related.sort(
            key=self._message_sort_key
        )

        if len(
            related
        ) <= self.related_message_limit:

            return related

        selected_time = str(
            selected_message.get(
                "sent_at"
            )
            or ""
        )

        if not selected_time:

            return related[
                -self.related_message_limit:
            ]

        related.sort(
            key=lambda message: abs(
                self._timestamp_distance(
                    str(
                        message.get(
                            "sent_at"
                        )
                        or ""
                    ),
                    selected_time,
                )
            )
        )

        selected_related = related[
            :self.related_message_limit
        ]

        selected_related.sort(
            key=self._message_sort_key
        )

        return selected_related

    def _filter_entities_for_message(
        self,
        *,
        entities: list[Any],
        values: set[str],
    ) -> list[dict[str, Any]]:
        """
        Find entities matching message participant values.
        """

        normalized_values = {
            value
            for value in values
            if value
        }

        if not normalized_values:

            return []

        result: list[
            dict[str, Any]
        ] = []

        for entity in entities:

            if not isinstance(
                entity,
                dict,
            ):

                continue

            entity_value = self._normalized_compare_text(
                entity.get(
                    "value"
                )
            )

            normalized_entity_value = (
                self._normalized_compare_text(
                    entity.get(
                        "normalized_value"
                    )
                )
            )

            if (
                entity_value in normalized_values
                or normalized_entity_value
                in normalized_values
            ):

                result.append(
                    entity
                )

        return result

    def _filter_timeline_for_message(
        self,
        *,
        timeline: list[Any],
        selected_message: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Find timeline events related to one message.
        """

        selected_id = self._normalized_compare_text(
            selected_message.get(
                "id"
            )
        )

        selected_external_id = (
            self._normalized_compare_text(
                selected_message.get(
                    "external_id"
                )
            )
        )

        selected_sent_at = self._normalized_compare_text(
            selected_message.get(
                "sent_at"
            )
        )

        result: list[
            dict[str, Any]
        ] = []

        for event in timeline:

            if not isinstance(
                event,
                dict,
            ):

                continue

            searchable_text = " ".join(
                str(
                    event.get(
                        key
                    )
                    or ""
                )
                for key in (
                    "id",
                    "title",
                    "description",
                    "date",
                    "event_time",
                )
            ).casefold()

            if (
                (
                    selected_id
                    and selected_id
                    in searchable_text
                )
                or (
                    selected_external_id
                    and selected_external_id
                    in searchable_text
                )
                or (
                    selected_sent_at
                    and selected_sent_at
                    == self._normalized_compare_text(
                        event.get(
                            "date"
                        )
                        or event.get(
                            "event_time"
                        )
                    )
                )
            ):

                result.append(
                    event
                )

        return result

    def _filter_evidence_for_message(
        self,
        *,
        evidence: list[Any],
        selected_message: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Find evidence related to one message.
        """

        evidence_id = self._normalized_compare_text(
            selected_message.get(
                "evidence_id"
            )
        )

        message_id = self._normalized_compare_text(
            selected_message.get(
                "id"
            )
        )

        external_id = self._normalized_compare_text(
            selected_message.get(
                "external_id"
            )
        )

        result: list[
            dict[str, Any]
        ] = []

        for item in evidence:

            if not isinstance(
                item,
                dict,
            ):

                continue

            item_id = self._normalized_compare_text(
                item.get(
                    "id"
                )
            )

            searchable_text = " ".join(
                str(
                    item.get(
                        key
                    )
                    or ""
                )
                for key in (
                    "id",
                    "title",
                    "value",
                    "file_path",
                )
            ).casefold()

            if (
                (
                    evidence_id
                    and item_id == evidence_id
                )
                or (
                    message_id
                    and message_id in searchable_text
                )
                or (
                    external_id
                    and external_id in searchable_text
                )
            ):

                result.append(
                    item
                )

        return result

    # ==========================================================
    # Helpers
    # ==========================================================

    def _empty_context(
        self,
        *,
        context_type: str,
    ) -> dict[str, Any]:
        """
        Create an empty compatible context structure.
        """

        return {
            "context_type": context_type,
            "case": {},
            "documents": [],
            "messages": [],
            "evidence": [],
            "entities": [],
            "relationships": [],
            "timeline": [],
            "reports": [],
            "analysis_results": [],
            "metadata": {
                "generated_at": datetime.now(
                    UTC
                ).isoformat(),
            },
        }

    @staticmethod
    def _normalize_workspace(
        workspace: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Normalize workspace input.
        """

        if workspace is None:

            return {}

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary or None."
            )

        return workspace

    @staticmethod
    def _get_list(
        source: dict[str, Any],
        key: str,
    ) -> list[Any]:
        """
        Return a list value safely.
        """

        value = source.get(
            key,
            [],
        )

        if isinstance(
            value,
            list,
        ):

            return value

        if isinstance(
            value,
            tuple,
        ):

            return list(
                value
            )

        return []

    def _build_metadata(
        self,
        *,
        normalized_workspace: dict[str, Any],
        included_counts: dict[str, int],
    ) -> dict[str, Any]:
        """
        Build context-generation metadata.
        """

        return {
            "generated_at": datetime.now(
                UTC
            ).isoformat(),
            "included_counts": included_counts,
            "workspace_statistics": (
                self._prepare_statistics(
                    normalized_workspace.get(
                        "statistics"
                    )
                )
            ),
            "limits": {
                "messages": self.max_messages,
                "related_messages": (
                    self.related_message_limit
                ),
                "evidence": self.max_evidence,
                "entities": self.max_entities,
                "relationships": (
                    self.max_relationships
                ),
                "timeline": (
                    self.max_timeline_events
                ),
                "reports": self.max_reports,
            },
        }

    def _build_participant_summary(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """
        Build sender, receiver and chat summaries.
        """

        return {
            "senders": sorted(
                {
                    str(
                        message.get(
                            "sender"
                        )
                    ).strip()
                    for message in messages
                    if str(
                        message.get(
                            "sender"
                        )
                        or ""
                    ).strip()
                },
                key=str.casefold,
            ),
            "receivers": sorted(
                {
                    str(
                        message.get(
                            "receiver"
                        )
                    ).strip()
                    for message in messages
                    if str(
                        message.get(
                            "receiver"
                        )
                        or ""
                    ).strip()
                },
                key=str.casefold,
            ),
            "chats": sorted(
                {
                    str(
                        message.get(
                            "chat_name"
                        )
                    ).strip()
                    for message in messages
                    if str(
                        message.get(
                            "chat_name"
                        )
                        or ""
                    ).strip()
                },
                key=str.casefold,
            ),
        }

    def _extend_context_list(
        self,
        *,
        key: str,
        values: list[dict[str, Any]],
        limit: int,
    ) -> None:
        """
        Safely extend a generic context list.
        """

        if not isinstance(
            values,
            list,
        ):

            raise TypeError(
                f"{key} must be a list."
            )

        prepared_values = [
            self._make_json_safe(
                value
            )
            for value in values
            if isinstance(
                value,
                dict,
            )
        ]

        self.context.setdefault(
            key,
            [],
        ).extend(
            prepared_values
        )

        self.context[key] = (
            self.context[key][
                :limit
            ]
        )

    def _normalize_metadata(
        self,
        value: Any,
    ) -> Any:
        """
        Parse metadata JSON where possible.
        """

        if value is None:

            return None

        if isinstance(
            value,
            (
                dict,
                list,
            ),
        ):

            return self._make_json_safe(
                value
            )

        if isinstance(
            value,
            str,
        ):

            stripped_value = value.strip()

            if not stripped_value:

                return None

            try:

                parsed_value = json.loads(
                    stripped_value
                )

            except json.JSONDecodeError:

                return self._truncate_text(
                    stripped_value,
                    self.text_limit,
                )

            return self._make_json_safe(
                parsed_value
            )

        return self._make_json_safe(
            value
        )

    def _truncate_text(
        self,
        value: Any,
        limit: int,
    ) -> str | None:
        """
        Normalize and truncate optional text.
        """

        if value is None:

            return None

        text = str(
            value
        ).strip()

        if not text:

            return None

        if len(
            text
        ) <= limit:

            return text

        omitted_count = (
            len(
                text
            )
            - limit
        )

        suffix = (
            f"\n...[truncated {omitted_count} characters]"
        )

        content_limit = max(
            0,
            limit
            - len(
                suffix
            ),
        )

        return (
            text[
                :content_limit
            ]
            + suffix
        )

    @staticmethod
    def _normalize_scalar(
        value: Any,
    ) -> Any:
        """
        Convert scalar values to JSON-safe representations.
        """

        if value is None:

            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            return value

        if isinstance(
            value,
            (
                UUID,
                datetime,
                date,
            ),
        ):

            return value.isoformat()

        return str(
            value
        )

    @staticmethod
    def _normalize_float(
        value: Any,
    ) -> float | None:
        """
        Normalize an optional numeric confidence.
        """

        if value is None:

            return None

        try:

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    def _make_json_safe(
        self,
        value: Any,
    ) -> Any:
        """
        Recursively convert values into JSON-compatible forms.
        """

        if value is None:

            return None

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            return value

        if isinstance(
            value,
            (
                UUID,
                datetime,
                date,
            ),
        ):

            return value.isoformat()

        if isinstance(
            value,
            dict,
        ):

            return {
                str(
                    key
                ): self._make_json_safe(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            return [
                self._make_json_safe(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            bytes,
        ):

            return value.decode(
                "utf-8",
                errors="replace",
            )

        return str(
            value
        )

    @staticmethod
    def _normalized_compare_text(
        value: Any,
    ) -> str:
        """
        Normalize text for comparisons.
        """

        return str(
            value
            or ""
        ).strip().casefold()

    @staticmethod
    def _message_sort_key(
        message: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build stable chronological message sort key.
        """

        return (
            str(
                message.get(
                    "sent_at"
                )
                or ""
            ),
            str(
                message.get(
                    "id"
                )
                or ""
            ),
        )

    @staticmethod
    def _timestamp_distance(
        first: str,
        second: str,
    ) -> float:
        """
        Calculate approximate timestamp distance in seconds.

        Invalid values are placed far away from the selected message.
        """

        try:

            first_datetime = datetime.fromisoformat(
                first.replace(
                    "Z",
                    "+00:00",
                )
            )

            second_datetime = datetime.fromisoformat(
                second.replace(
                    "Z",
                    "+00:00",
                )
            )

            return (
                first_datetime
                - second_datetime
            ).total_seconds()

        except (
            TypeError,
            ValueError,
        ):

            return float(
                "inf"
            )

    @staticmethod
    def _normalize_positive_limit(
        value: int,
        *,
        field_name: str,
    ) -> int:
        """
        Validate a positive integer limit.
        """

        try:

            normalized_value = int(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                f"{field_name} must be an integer."
            ) from error

        if normalized_value <= 0:

            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized_value