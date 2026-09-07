"""
AI investigation service.

Runs AI analysis workflows for investigation data.

Responsible for:

- building bounded AI context
- rendering investigation prompts
- executing AI requests
- storing AI analysis results
- returning UI-ready analysis data

Does NOT:

- collect OSINT data
- build entity graphs
- generate report files
- commit or roll back transactions
- contain desktop UI logic
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.ai_manager import (
    AIManager,
)

from app.ai.context.context_builder import (
    ContextBuilder,
)

from app.ai.prompts.prompt_manager import (
    PromptManager,
)

from app.models.ai_analysis import (
    AIAnalysis,
    AnalysisType,
)

from app.repositories.ai_analysis_repository import (
    AIAnalysisRepository,
)


class AIInvestigationService:
    """
    High-level AI workflow service for investigations.
    """

    def __init__(
        self,
        session: Session,
        ai_manager: AIManager,
        context_builder: ContextBuilder | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> None:

        self.session = session

        self.ai_manager = ai_manager

        self.context_builder = (
            context_builder
            or ContextBuilder()
        )

        self.prompt_manager = (
            prompt_manager
            or PromptManager()
        )

        self.repository = AIAnalysisRepository(
            session
        )

    # ==========================================================
    # Message analysis
    # ==========================================================

    def analyze_message(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
        message_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze one message in investigation context.

        The result is saved as AIAnalysis but the transaction is not
        committed here. Transaction control remains at page/container
        level.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        if not isinstance(
            message_data,
            dict,
        ):

            raise TypeError(
                "message_data must be a dictionary."
            )

        self._ensure_ai_ready()

        context = (
            self.context_builder
            .build_message_context(
                workspace=workspace,
                message=message_data,
            )
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                "message_analysis",
                {
                    "case_context": (
                        self.context_builder
                        .to_prompt_text(
                            {
                                "case": context.get(
                                    "case",
                                    {},
                                ),
                            }
                        )
                    ),
                    "message": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "selected_message",
                                {},
                            )
                        )
                    ),
                    "related_context": (
                        self.context_builder
                        .to_prompt_text(
                            {
                                "previous_messages": (
                                    context.get(
                                        "previous_messages",
                                        [],
                                    )
                                ),
                                "next_messages": (
                                    context.get(
                                        "next_messages",
                                        [],
                                    )
                                ),
                                "related_entities": (
                                    context.get(
                                        "related_entities",
                                        [],
                                    )
                                ),
                                "related_relationships": (
                                    context.get(
                                        "related_relationships",
                                        [],
                                    )
                                ),
                                "related_evidence": (
                                    context.get(
                                         "related_evidence",
                                        [],
                                    )
                                ),
                                "related_timeline": (
                                    context.get(
                                        "related_timeline",
                                        [],
                                    )
                                ),
                            }
                        )
                    )
                },
            )
        )

        response = self.ai_manager.generate(
            prompt
        )

        normalized_response = self._normalize_response(
            response
        )

        model_info = self.ai_manager.info()

        analysis = self._store_analysis(
            case_id=case_uuid,
            analysis_type=AnalysisType.OTHER,
            result=normalized_response,
            model_name=self._extract_model_name(
                model_info
            ),
            metadata={
                "workflow": "message_analysis",
                "source_type": "message",
                "source": {
                    "message_id": message_data.get(
                        "id"
                    ),
                    "external_id": message_data.get(
                        "external_id"
                    ),
                    "source_id": message_data.get(
                        "source_id"
                    ),
                },
                "provider": (
                    self.ai_manager.metadata()
                ),
                "model_info": model_info,
                "context": (
                    self.context_builder
                    .summarize_context()
                ),
                "prompt": {
                    "name": "message_analysis",
                    "characters": len(
                        prompt
                    ),
                },
            },
        )

        return self._serialize_analysis(
            analysis
        )

    # ==========================================================
    # Message collection analysis
    # ==========================================================

    def analyze_message_collection(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze a selected collection of messages.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        self._ensure_ai_ready()

        context = (
            self.context_builder
            .build_message_collection_context(
                workspace=workspace,
                messages=messages,
            )
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                "conversation_summary",
                {
                    "case_context": (
                        self.context_builder
                        .to_prompt_text(
                            {
                                "case": context.get(
                                    "case",
                                    {},
                                ),
                            }
                        )
                    ),
                    "messages": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "messages",
                                [],
                            )
                        )
                    ),
                },
            )
        )

        response = self.ai_manager.generate(
            prompt
        )

        normalized_response = self._normalize_response(
            response
        )

        model_info = self.ai_manager.info()

        analysis = self._store_analysis(
            case_id=case_uuid,
            analysis_type=(
                AnalysisType.SUMMARIZATION
            ),
            result=normalized_response,
            model_name=self._extract_model_name(
                model_info
            ),
            metadata={
                "workflow": "conversation_summary",
                "source_type": "message_collection",
                "source": {
                    "message_count": len(
                        context.get(
                            "messages",
                            [],
                        )
                    ),
                    "message_ids": [
                        message.get(
                            "id"
                        )
                        for message in context.get(
                            "messages",
                            [],
                        )
                        if isinstance(
                            message,
                            dict,
                        )
                    ],
                },
                "provider": (
                    self.ai_manager.metadata()
                ),
                "model_info": model_info,
                "context": (
                    self.context_builder
                    .summarize_context()
                ),
                "prompt": {
                    "name": "conversation_summary",
                    "characters": len(
                        prompt
                    ),
                },
            },
        )

        return self._serialize_analysis(
            analysis
        )

    # ==========================================================
    # Investigation analysis
    # ==========================================================

    def analyze_investigation(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze the complete bounded investigation workspace.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        self._ensure_ai_ready()

        context = (
            self.context_builder
            .build_investigation_context(
                workspace
            )
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                "investigation_summary",
                {
                    "case": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "case",
                                {},
                            )
                        )
                    ),
                    "messages": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "messages",
                                [],
                            )
                        )
                    ),
                    "evidence": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "evidence",
                                [],
                            )
                        )
                    ),
                    "entities": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "entities",
                                [],
                            )
                        )
                    ),
                    "relationships": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "relationships",
                                [],
                            )
                        )
                    ),
                    "timeline": (
                        self.context_builder
                        .to_prompt_text(
                            context.get(
                                "timeline",
                                [],
                            )
                        )
                    ),
                },
            )
        )

        response = self.ai_manager.generate(
            prompt
        )

        normalized_response = self._normalize_response(
            response
        )

        model_info = self.ai_manager.info()

        analysis = self._store_analysis(
            case_id=case_uuid,
            analysis_type=(
                AnalysisType.SUMMARIZATION
            ),
            result=normalized_response,
            model_name=self._extract_model_name(
                model_info
            ),
            metadata={
                "workflow": "investigation_summary",
                "source_type": "investigation",
                "provider": (
                    self.ai_manager.metadata()
                ),
                "model_info": model_info,
                "context": (
                    self.context_builder
                    .summarize_context()
                ),
                "prompt": {
                    "name": "investigation_summary",
                    "characters": len(
                        prompt
                    ),
                },
            },
        )

        return self._serialize_analysis(
            analysis
        )

    # ==========================================================
    # Analysis history
    # ==========================================================

    def get_case_analyses(
        self,
        case_id: str | UUID,
    ) -> list[dict[str, Any]]:
        """
        Return serialized AI analyses for a case.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        analyses = self.repository.get_by_case(
            case_uuid
        )

        return [
            self._serialize_analysis(
                analysis
            )
            for analysis in analyses
        ]

    def get_latest_analysis(
        self,
        case_id: str | UUID,
    ) -> dict[str, Any] | None:
        """
        Return the latest AI analysis for a case.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        analysis = self.repository.get_latest(
            case_uuid
        )

        if analysis is None:

            return None

        return self._serialize_analysis(
            analysis
        )

    # ==========================================================
    # Persistence
    # ==========================================================

    def _store_analysis(
        self,
        *,
        case_id: UUID,
        analysis_type: AnalysisType,
        result: str,
        model_name: str | None,
        metadata: dict[str, Any],
    ) -> AIAnalysis:
        """
        Store one AI analysis without committing the transaction.
        """

        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            default=str,
        )

        return self.repository.create(
            case_id=case_id,
            analysis_type=analysis_type,
            model_name=model_name,
            result=result,
            confidence=None,
            metadata_json=metadata_json,
        )

    # ==========================================================
    # Provider state
    # ==========================================================

    # ==========================================================
    # Generic text execution
    # ==========================================================

    def generate_text(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """
        Execute one already-rendered prompt through the
        configured AI provider.

        This is the public low-level execution contract for
        higher-level AI/RAG orchestration services.

        It does NOT create or persist AIAnalysis records.
        Persistence remains the responsibility of explicit
        analysis workflows.
        """

        normalized_prompt = str(
            prompt
            or ""
        ).strip()

        if not normalized_prompt:

            raise ValueError(
                "AI prompt cannot be empty."
            )

        self._ensure_ai_ready()

        response = self.ai_manager.generate(
            normalized_prompt,
            **kwargs,
        )

        return self._normalize_response(
            response
        )


    def _ensure_ai_ready(
        self,
    ) -> None:
        """
        Initialize and connect the configured provider when needed.
        """

        if self.ai_manager.provider is None:

            self.ai_manager.initialize()

        if not self.ai_manager.health_check():

            connected = self.ai_manager.connect()

            if not connected:

                raise RuntimeError(
                    "The configured AI provider is unavailable."
                )

    # ==========================================================
    # Serialization
    # ==========================================================

    @staticmethod
    def _serialize_analysis(
        analysis: AIAnalysis,
    ) -> dict[str, Any]:
        """
        Convert AIAnalysis into UI-ready data.
        """

        metadata: Any = None

        if analysis.metadata_json:

            try:

                metadata = json.loads(
                    analysis.metadata_json
                )

            except json.JSONDecodeError:

                metadata = (
                    analysis.metadata_json
                )

        return {
            "id": str(
                analysis.id
            ),
            "case_id": str(
                analysis.case_id
            ),
            "type": (
                analysis.analysis_type.value
            ),
            "model": analysis.model_name,
            "result": analysis.result,
            "confidence": analysis.confidence,
            "metadata": metadata,
            "created_at": (
                analysis.created_at.isoformat()
                if analysis.created_at
                else None
            ),
        }

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalize_uuid(
        value: str | UUID,
        *,
        field_name: str,
    ) -> UUID:
        """
        Convert an identifier to UUID.
        """

        if isinstance(
            value,
            UUID,
        ):

            return value

        try:

            return UUID(
                str(
                    value
                )
            )

        except (
            TypeError,
            ValueError,
            AttributeError,
        ) as error:

            raise ValueError(
                f"{field_name} must contain a valid UUID."
            ) from error

    @staticmethod
    def _normalize_response(
        response: Any,
    ) -> str:
        """
        Validate and normalize an AI response.
        """

        normalized_response = str(
            response
            or ""
        ).strip()

        if not normalized_response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        return normalized_response

    @staticmethod
    def _extract_model_name(
        model_info: dict[str, Any] | None,
    ) -> str | None:
        """
        Extract model name from provider information.
        """

        if not isinstance(
            model_info,
            dict,
        ):

            return None

        model_name = str(
            model_info.get(
                "model"
            )
            or ""
        ).strip()

        if not model_name:

            return None

        return model_name[
            :100
        ]