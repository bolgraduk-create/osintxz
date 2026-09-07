"""
AI analysis controller.

Responsible for:

- receiving AI requests from the desktop UI
- validating investigation identifiers and input data
- delegating structured workflows to AIInvestigationService
- preserving legacy RAG-powered AI operations
- returning UI-ready analysis results

Does NOT:

- execute AI models directly
- access repositories
- manage database transactions
- build prompts or AI context
- contain desktop widget logic
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.ai.analysis.ai_analyzer import (
    AIAnalyzer,
)

from app.ai.providers.ai_investigation_service import (
    AIInvestigationService,
)

from app.application.investigation_ai_service import (
    InvestigationAIService,
)


class AIAnalysisController:
    """
    Controller for AI operations.

    Two complementary AI paths are exposed:

    - structured, persistent investigation workflows through
      AIInvestigationService;
    - legacy and RAG-powered operations through AIAnalyzer.
    """

    def __init__(
        self,
        investigation_service: InvestigationAIService,
        execution_service: AIInvestigationService,
        analyzer: AIAnalyzer,
    ) -> None:

        self.investigation_service = (
            investigation_service
        )

        self.execution_service = (
            execution_service
        )

        self.analyzer = analyzer

    # ==========================================================
    # Validation
    # ==========================================================

    def can_analyze(
        self,
        case_id: str | UUID,
    ) -> bool:
        """
        Check whether a case can be analyzed.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        return (
            self.investigation_service
            .can_analyze(
                case_uuid
            )
        )

    # ==========================================================
    # Case
    # ==========================================================

    def get_case(
        self,
        case_id: str | UUID,
    ):
        """
        Return the selected case.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        return (
            self.investigation_service
            .get_case(
                case_uuid
            )
        )

    # ==========================================================
    # Structured investigation AI
    # ==========================================================

    def analyze_message(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
        message_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze one message using bounded investigation context.

        The execution service stores an AIAnalysis record but does
        not commit the transaction.
        """

        case_uuid = self._validate_analysis_request(
            case_id=case_id,
            workspace=workspace,
        )

        if not isinstance(
            message_data,
            dict,
        ):

            raise TypeError(
                "message_data must be a dictionary."
            )

        if not message_data:

            raise ValueError(
                "message_data cannot be empty."
            )

        return (
            self.execution_service
            .analyze_message(
                case_id=case_uuid,
                workspace=workspace,
                message_data=message_data,
            )
        )

    def analyze_message_collection(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze a selected collection of messages.
        """

        case_uuid = self._validate_analysis_request(
            case_id=case_id,
            workspace=workspace,
        )

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        normalized_messages = [
            dict(
                message
            )
            for message in messages
            if isinstance(
                message,
                dict,
            )
            and message
        ]

        if not normalized_messages:

            raise ValueError(
                "No valid messages were provided."
            )

        return (
            self.execution_service
            .analyze_message_collection(
                case_id=case_uuid,
                workspace=workspace,
                messages=normalized_messages,
            )
        )

    def analyze_investigation(
        self,
        case_id: str | UUID,
        workspace: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze the complete bounded investigation workspace.
        """

        case_uuid = self._validate_analysis_request(
            case_id=case_id,
            workspace=workspace,
        )

        return (
            self.execution_service
            .analyze_investigation(
                case_id=case_uuid,
                workspace=workspace,
            )
        )

    def ask_about_workspace(
        self,
        *,
        case_id: str | UUID,
        workspace: dict[str, Any],
        question: str,
    ) -> str:
        """
        Ask AI a question about the active investigation.
        """

        case_uuid = self._validate_analysis_request(
            case_id=case_id,
            workspace=workspace,
        )

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:

            raise ValueError(
                "question cannot be empty."
            )

        result = (
            self.analyzer
            .ask_about_workspace(
                workspace=workspace,
                question=normalized_question,
            )
        )

        return self._extract_rag_response(
            result
        )

    def execute_workspace_question(
        self,
        *,
        workspace: dict[str, Any],
        question: str,
    ) -> str:
        """
        Execute a workspace AI question without database access.
        """

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        if not workspace:

            raise ValueError(
                "workspace cannot be empty."
            )

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:

            raise ValueError(
                "question cannot be empty."
            )

        case_data = workspace.get(
            "case",
            {}
        )

        if not isinstance(
            case_data,
            dict,
        ):

            raise ValueError(
                "workspace does not contain valid case data."
            )

        case_id = str(
            case_data.get(
                "id"
            )
            or ""
        ).strip()

        if not case_id:

            raise ValueError(
                "workspace case identifier is missing."
            )

        result = (
            self.analyzer
            .ask_about_workspace(
                case_id=case_id,
                workspace=workspace,
                question=normalized_question,
            )
        )

        return self._extract_rag_response(
            result
        )

    def execute_workflow(
        self,
        *,
        workspace: dict[str, Any],
        workflow_name: str,
    ) -> str:
        """
        Execute one predefined AI workflow.
        """

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        if not workspace:

            raise ValueError(
                "workspace cannot be empty."
            )

        normalized_workflow_name = str(
            workflow_name
            or ""
        ).strip()

        if not normalized_workflow_name:

            raise ValueError(
                "workflow_name cannot be empty."
            )

        case_data = workspace.get(
            "case",
            {}
        )

        if not isinstance(
            case_data,
            dict,
        ):

            raise ValueError(
                "workspace does not contain valid case data."
            )

        case_id = str(
            case_data.get(
                "id"
            )
            or ""
        ).strip()

        if not case_id:

            raise ValueError(
                "workspace case identifier is missing."
            )

        result = (
            self.analyzer
            .execute_workflow(
                case_id=case_id,
                workspace=workspace,
                workflow_name=normalized_workflow_name,
            )
        )

        if not isinstance(
            result,
            dict,
        ):

            return str(
                result
            )

        response = str(
            result.get(
                "response"
            )
            or ""
        ).strip()

        if not response:

            raise ValueError(
                "The AI workflow returned an empty response."
            )

        return response

    # ==========================================================
    # Analysis history
    # ==========================================================

    def get_case_analyses(
        self,
        case_id: str | UUID,
    ) -> list[dict[str, Any]]:
        """
        Return all stored AI analyses for a case.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        return (
            self.execution_service
            .get_case_analyses(
                case_uuid
            )
        )

    def get_latest_analysis(
        self,
        case_id: str | UUID,
    ) -> dict[str, Any] | None:
        """
        Return the latest stored AI analysis for a case.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        return (
            self.execution_service
            .get_latest_analysis(
                case_uuid
            )
        )

    # ==========================================================
    # Legacy RAG-powered operations
    # ==========================================================

    def ask(
        self,
        question: str,
    ) -> str:
        """
        Ask the RAG-powered AI assistant.
        """

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:

            raise ValueError(
                "question cannot be empty."
            )

        result = (
            self.analyzer
            .ask(
                normalized_question
            )
        )

        return self._extract_rag_response(
            result
        )

    def analyze_case(
        self,
        case: dict[str, Any],
    ) -> str:
        """
        Run the legacy RAG case analysis.
        """

        if not isinstance(
            case,
            dict,
        ):

            raise TypeError(
                "case must be a dictionary."
            )

        if not case:

            raise ValueError(
                "case cannot be empty."
            )

        result = (
            self.analyzer
            .analyze_case(
                case
            )
        )

        return self._extract_rag_response(
            result
        )

    def analyze_document(
        self,
        document: dict[str, Any],
    ) -> str:
        """
        Run the legacy RAG document analysis.
        """

        if not isinstance(
            document,
            dict,
        ):

            raise TypeError(
                "document must be a dictionary."
            )

        if not document:

            raise ValueError(
                "document cannot be empty."
            )

        result = (
            self.analyzer
            .analyze_document(
                document
            )
        )

        return self._extract_rag_response(
            result
        )

    def analyze_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> str:
        """
        Run the legacy RAG analysis for a message collection.

        New desktop workflows should normally use
        analyze_message_collection(), because it builds bounded case
        context and stores the resulting AIAnalysis.
        """

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        normalized_messages = [
            dict(
                message
            )
            for message in messages
            if isinstance(
                message,
                dict,
            )
            and message
        ]

        if not normalized_messages:

            raise ValueError(
                "No valid messages were provided."
            )

        result = (
            self.analyzer
            .analyze_messages(
                normalized_messages
            )
        )

        return self._extract_rag_response(
            result
        )

    # ==========================================================
    # Validation helpers
    # ==========================================================

    def _validate_analysis_request(
        self,
        *,
        case_id: str | UUID,
        workspace: dict[str, Any],
    ) -> UUID:
        """
        Validate a structured AI analysis request.
        """

        case_uuid = self._normalize_uuid(
            case_id,
            field_name="case_id",
        )

        if not self.can_analyze(
            case_uuid
        ):

            raise ValueError(
                "The selected investigation cannot be analyzed."
            )

        if not isinstance(
            workspace,
            dict,
        ):

            raise TypeError(
                "workspace must be a dictionary."
            )

        if not workspace:

            raise ValueError(
                "workspace cannot be empty."
            )

        workspace_case = workspace.get(
            "case"
        )

        if isinstance(
            workspace_case,
            dict,
        ):

            workspace_case_id = (
                workspace_case.get(
                    "id"
                )
            )

            if workspace_case_id is not None:

                normalized_workspace_case_id = (
                    self._normalize_uuid(
                        workspace_case_id,
                        field_name=(
                            "workspace case id"
                        ),
                    )
                )

                if (
                    normalized_workspace_case_id
                    != case_uuid
                ):

                    raise ValueError(
                        "Workspace data belongs to another case."
                    )

        return case_uuid

    # ==========================================================
    # General helpers
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
    def _extract_rag_response(
        result: Any,
    ) -> str:
        """
        Extract and validate text returned by AIAnalyzer.
        """

        if not isinstance(
            result,
            dict,
        ):

            raise TypeError(
                "AIAnalyzer returned an invalid result."
            )

        response = str(
            result.get(
                "response"
            )
            or ""
        ).strip()

        if not response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        return response

def execute_workflow(
    self,
    *,
    workspace: dict[str, Any],
    workflow_name: str,
) -> str:
    """
    Execute one predefined AI workflow.
    """

    case = workspace.get(
        "case",
        {}
    )

    case_id = str(
        case.get(
            "id",
            "",
        )
    )

    result = (
        self.analyzer
        .execute_workflow(
            case_id=case_id,
            workspace=workspace,
            workflow_name=workflow_name,
        )
    )

    return result.get(
        "response",
        "",
    )