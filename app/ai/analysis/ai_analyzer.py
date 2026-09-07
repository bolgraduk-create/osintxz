"""
AI Analyzer.

Execution layer for AI-powered investigation analysis.

Responsible for:

- preparing AI requests
- building bounded workspace context
- using retrieved RAG knowledge
- rendering investigation prompts
- executing AI generation
- returning structured results

Does NOT:

- store data
- access database
- replace the investigation pipeline
- contain desktop UI logic
"""

from __future__ import annotations

from typing import Any

from app.ai.context.context_builder import (
    ContextBuilder,
)

from app.ai.prompts.prompt_manager import (
    PromptManager,
)

from app.ai.rag.rag_engine import (
    RAGEngine,
)

from app.ai.context import (
    ConversationMemory,
)


class AIAnalyzer:
    """
    Main AI analysis executor.
    """

    def __init__(
        self,
        rag_engine: RAGEngine,
        context_builder: ContextBuilder | None = None,
        prompt_manager: PromptManager | None = None,
        conversation_memory: ConversationMemory | None = None,
    ) -> None:

        self.rag_engine = rag_engine

        self.context_builder = (
            context_builder
            or ContextBuilder()
        )

        self.prompt_manager = (
            prompt_manager
            or PromptManager()
        )

        self.conversation_memory = (
            conversation_memory
            or ConversationMemory()
        )

    # ==========================================================
    # Generic analysis
    # ==========================================================

    def analyze(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute generic AI analysis.
        """

        if not isinstance(
            data,
            dict,
        ):

            raise TypeError(
                "data must be a dictionary."
            )

        analysis_type = str(
            data.get(
                "type",
                "general",
            )
            or "general"
        ).strip()

        content = str(
            data.get(
                "content",
                "",
            )
            or ""
        ).strip()

        if not content:

            raise ValueError(
                "Analysis content cannot be empty."
            )

        question = (
            f"Perform {analysis_type} "
            "investigation analysis.\n\n"
            f"Data:\n{content}"
        )

        return self.rag_engine.query(
            question
        )

    # ==========================================================
    # Case analysis
    # ==========================================================

    def analyze_case(
        self,
        case: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze an investigation case.
        """

        if not isinstance(
            case,
            dict,
        ):

            raise TypeError(
                "case must be a dictionary."
            )

        return self.analyze(
            {
                "type": "case",
                "content": str(
                    case
                ),
            }
        )

    # ==========================================================
    # Document analysis
    # ==========================================================

    def analyze_document(
        self,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze a document.
        """

        if not isinstance(
            document,
            dict,
        ):

            raise TypeError(
                "document must be a dictionary."
            )

        return self.analyze(
            {
                "type": "document",
                "content": document.get(
                    "content",
                    "",
                ),
            }
        )

    # ==========================================================
    # Message analysis
    # ==========================================================

    def analyze_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze a message collection.
        """

        if not isinstance(
            messages,
            list,
        ):

            raise TypeError(
                "messages must be a list."
            )

        content = "\n".join(
            str(
                message.get(
                    "text",
                    "",
                )
                or ""
            ).strip()
            for message in messages
            if isinstance(
                message,
                dict,
            )
        ).strip()

        if not content:

            raise ValueError(
                "The message collection contains no text."
            )

        return self.analyze(
            {
                "type": "messages",
                "content": content,
            }
        )

    # ==========================================================
    # Questions
    # ==========================================================

    def ask(
        self,
        question: str,
    ) -> dict[str, Any]:
        """
        Ask a general RAG-powered investigation question.
        """

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:

            raise ValueError(
                "question cannot be empty."
            )

        return self.rag_engine.query(
            normalized_question
        )

    def ask_about_workspace(
        self,
        *,
        workspace: dict[str, Any],
        question: str,
        retrieval_limit: int = 5,
    ) -> dict[str, Any]:
        """
        Answer a question using the active investigation workspace.

        Combines:

        - bounded CaseWorkspace context
        - knowledge retrieved by RAG
        - the investigation_chat prompt
        - the shared configured AI provider
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

        try:

            normalized_limit = int(
                retrieval_limit
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "retrieval_limit must be an integer."
            ) from error

        if normalized_limit <= 0:

            raise ValueError(
                "retrieval_limit must be greater than zero."
            )

        investigation_context = (
            self.context_builder
            .build_investigation_context(
                workspace
            )
        )

        retrieved_context = (
            self.rag_engine
            .retrieve_context(
                query=normalized_question,
                limit=normalized_limit,
            )
        )

        workspace_context_text = (
            self.context_builder
            .to_prompt_text(
                investigation_context
            )
        )

        retrieved_context_text = (
            self.context_builder
            .to_prompt_text(
                {
                    "items": retrieved_context,
                }
            )
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                "investigation_chat",
                {
                    "workspace_context": (
                        workspace_context_text
                    ),
                    "retrieved_context": (
                        retrieved_context_text
                    ),
                    "question": (
                        normalized_question
                    ),
                },
            )
        )

        response = (
            self.rag_engine
            .ai
            .generate(
                prompt
            )
        )

        normalized_response = str(
            response
            or ""
        ).strip()

        if not normalized_response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        return {
            "question": normalized_question,
            "context": investigation_context,
            "retrieved_context": retrieved_context,
            "response": normalized_response,
            "metadata": {
                "workflow": "investigation_chat",
                "prompt_characters": len(
                    prompt
                ),
                "workspace_context": (
                    self.context_builder
                    .summarize_context()
                ),
                "retrieved_items": len(
                    retrieved_context
                ),
            },
        }

    def ask_about_workspace(
        self,
        *,
        case_id: str,
        workspace: dict[str, Any],
        question: str,
        retrieval_limit: int = 5,
    ) -> dict[str, Any]:
        """
        Answer a question using the active investigation workspace
        and recent conversation history.
        """

        normalized_case_id = str(
            case_id
            or ""
        ).strip()

        if not normalized_case_id:

            raise ValueError(
                "case_id cannot be empty."
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

        normalized_question = str(
            question
            or ""
        ).strip()

        if not normalized_question:

            raise ValueError(
                "question cannot be empty."
            )

        try:

            normalized_limit = int(
                retrieval_limit
            )

        except (
            TypeError,
            ValueError,
        ) as error:

            raise ValueError(
                "retrieval_limit must be an integer."
            ) from error

        if normalized_limit <= 0:

            raise ValueError(
                "retrieval_limit must be greater than zero."
            )

        investigation_context = (
            self.context_builder
            .build_investigation_context(
                workspace
            )
        )

        retrieved_context = (
            self.rag_engine
            .retrieve_context(
                query=normalized_question,
                limit=normalized_limit,
            )
        )

        conversation_history = (
            self.conversation_memory
            .get_prompt_history(
                normalized_case_id,
                limit=8,
            )
        )

        workspace_context_text = (
            self.context_builder
            .to_prompt_text(
                investigation_context
            )
        )

        retrieved_context_text = (
            self.context_builder
            .to_prompt_text(
                {
                    "items": retrieved_context,
                }
            )
        )

        conversation_history_text = (
            self.context_builder
            .to_prompt_text(
                {
                    "messages": (
                        conversation_history
                    ),
                }
            )
            if conversation_history
            else "No previous conversation."
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                "investigation_chat",
                {
                    "workspace_context": (
                        workspace_context_text
                    ),
                    "retrieved_context": (
                        retrieved_context_text
                    ),
                    "conversation_history": (
                        conversation_history_text
                    ),
                    "question": (
                        normalized_question
                    ),
                },
            )
        )

        response = (
            self.rag_engine
            .ai
            .generate(
                prompt
            )
        )

        normalized_response = str(
            response
            or ""
        ).strip()

        if not normalized_response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        self.conversation_memory.add_user_message(
            normalized_case_id,
            normalized_question,
            metadata={
                "workflow": (
                    "investigation_chat"
                ),
            },
        )

        self.conversation_memory.add_assistant_message(
            normalized_case_id,
            normalized_response,
            metadata={
                "workflow": (
                    "investigation_chat"
                ),
                "retrieved_items": len(
                    retrieved_context
                ),
            },
        )

        return {
            "question": normalized_question,
            "context": investigation_context,
            "retrieved_context": retrieved_context,
            "conversation_history": (
                conversation_history
            ),
            "response": normalized_response,
            "metadata": {
                "workflow": (
                    "investigation_chat"
                ),
                "prompt_characters": len(
                    prompt
                ),
                "workspace_context": (
                    self.context_builder
                    .summarize_context()
                ),
                "conversation_messages": len(
                    conversation_history
                ),
                "retrieved_items": len(
                    retrieved_context
                ),
            },
        }

    def execute_workflow(
        self,
        *,
        case_id: str,
        workspace: dict[str, Any],
        workflow_name: str,
    ) -> dict[str, Any]:
        """
        Execute one predefined AI workflow.

        Builds the variables required by the selected prompt,
        generates the response and adds it to conversation memory.
        """

        normalized_case_id = str(
            case_id
            or ""
        ).strip()

        if not normalized_case_id:

            raise ValueError(
                "case_id cannot be empty."
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

        normalized_workflow_name = str(
            workflow_name
            or ""
        ).strip()

        if not normalized_workflow_name:

            raise ValueError(
                "workflow_name cannot be empty."
            )

        supported_workflows = {
            "investigation_summary",
            "contradiction_analysis",
            "relationship_analysis",
            "timeline_analysis",
            "hypothesis_generation",
            "next_investigation_steps",
        }

        if (
            normalized_workflow_name
            not in supported_workflows
        ):

            raise ValueError(
                "Unsupported AI workflow: "
                f"{normalized_workflow_name}"
            )

        investigation_context = (
            self.context_builder
            .build_investigation_context(
                workspace
            )
        )

        case_context = (
            investigation_context.get(
                "case",
                {},
            )
        )

        messages_context = (
            investigation_context.get(
                "messages",
                [],
            )
        )

        evidence_context = (
            investigation_context.get(
                "evidence",
                [],
            )
        )

        entities_context = (
            investigation_context.get(
                "entities",
                [],
            )
        )

        relationships_context = (
            investigation_context.get(
                "relationships",
                [],
            )
        )

        timeline_context = (
            investigation_context.get(
                "timeline",
                [],
            )
        )

        reports_context = (
            investigation_context.get(
                "reports",
                [],
            )
        )

        complete_context_text = (
            self.context_builder
            .to_prompt_text(
                investigation_context
            )
        )

        supporting_context_text = (
            self.context_builder
            .to_prompt_text(
                {
                    "messages": (
                        messages_context
                    ),
                    "evidence": (
                        evidence_context
                    ),
                    "reports": (
                        reports_context
                    ),
                }
            )
        )

        workflow_variables: dict[
            str,
            dict[str, Any],
        ] = {
            "investigation_summary": {
                "case": (
                    case_context
                ),
                "messages": (
                    messages_context
                ),
                "evidence": (
                    evidence_context
                ),
                "entities": (
                    entities_context
                ),
                "relationships": (
                    relationships_context
                ),
                "timeline": (
                    timeline_context
                ),
            },

            "contradiction_analysis": {
                "context": (
                    complete_context_text
                ),
            },

            "relationship_analysis": {
                "entities": (
                    entities_context
                ),
                "relationships": (
                    relationships_context
                ),
                "supporting_context": (
                    supporting_context_text
                ),
            },

            "timeline_analysis": {
                "timeline": (
                    timeline_context
                ),
                "entities": (
                    entities_context
                ),
                "supporting_context": (
                    supporting_context_text
                ),
            },

            "hypothesis_generation": {
                "context": (
                    complete_context_text
                ),
            },

            "next_investigation_steps": {
                "context": (
                    complete_context_text
                ),
            },
        }

        prompt_variables = (
            workflow_variables[
                normalized_workflow_name
            ]
        )

        prompt = (
            self.prompt_manager
            .render_prompt(
                normalized_workflow_name,
                prompt_variables,
            )
        )

        response = (
            self.rag_engine
            .ai
            .generate(
                prompt
            )
        )

        normalized_response = str(
            response
            or ""
        ).strip()

        if not normalized_response:

            raise ValueError(
                "The AI provider returned an empty response."
            )

        self.conversation_memory.add_system_message(
            normalized_case_id,
            (
                "AI workflow executed: "
                f"{normalized_workflow_name}"
            ),
            metadata={
                "workflow": (
                    normalized_workflow_name
                ),
            },
        )

        self.conversation_memory.add_assistant_message(
            normalized_case_id,
            normalized_response,
            metadata={
                "workflow": (
                    normalized_workflow_name
                ),
                "prompt_characters": len(
                    prompt
                ),
            },
        )

        return {
            "workflow": (
                normalized_workflow_name
            ),
            "response": (
                normalized_response
            ),
            "metadata": {
                "prompt_characters": len(
                    prompt
                ),
                "context": (
                    self.context_builder
                    .summarize_context()
                ),
            },
        }

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return analyzer information.
        """

        return {
            "type": "ai_analyzer",
            "rag_engine": (
                self.rag_engine.metadata()
            ),
            "context_builder": (
                self.context_builder.metadata()
            ),
            "prompt_manager": (
                self.prompt_manager.metadata()
            ),
        }