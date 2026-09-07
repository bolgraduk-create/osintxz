"""
Prompt Manager.

Responsible for:

- registering AI prompt templates
- storing prompt metadata
- validating prompt variables
- rendering investigation prompts
- exposing available AI workflows

Does NOT:

- call AI providers
- access database
- collect investigation data
- execute business logic
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC
from datetime import datetime
from string import Formatter
from typing import Any


class PromptManager:
    """
    Central registry and renderer for AI prompt templates.

    Prompt templates are grouped by investigation workflow and
    rendered using named variables.
    """

    def __init__(
        self,
    ) -> None:

        self.prompts: dict[
            str,
            dict[str, Any],
        ] = {}

        self._formatter = Formatter()

        self._load_default_prompts()

    # ==========================================================
    # Registration
    # ==========================================================

    def register_prompt(
        self,
        name: str,
        template: str,
        description: str = "",
        version: str = "1.0",
        category: str = "general",
        required_variables: tuple[str, ...] | None = None,
    ) -> None:
        """
        Register or replace a prompt template.

        Args:
            name:
                Unique prompt identifier.

            template:
                Format-string template containing named fields.

            description:
                Human-readable explanation of the workflow.

            version:
                Prompt version.

            category:
                Logical prompt category.

            required_variables:
                Explicit required variable names. When omitted,
                variables are extracted from the template.
        """

        normalized_name = self._normalize_identifier(
            name,
            field_name="name",
        )

        normalized_category = self._normalize_identifier(
            category,
            field_name="category",
        )

        normalized_template = str(
            template
        ).strip()

        if not normalized_template:

            raise ValueError(
                "Prompt template cannot be empty."
            )

        normalized_version = str(
            version
        ).strip()

        if not normalized_version:

            raise ValueError(
                "Prompt version cannot be empty."
            )

        template_variables = (
            self._extract_template_variables(
                normalized_template
            )
        )

        if required_variables is None:

            normalized_required_variables = (
                template_variables
            )

        else:

            normalized_required_variables = tuple(
                self._normalize_identifier(
                    variable,
                    field_name="required variable",
                )
                for variable in required_variables
            )

            missing_from_template = (
                set(
                    normalized_required_variables
                )
                - set(
                    template_variables
                )
            )

            if missing_from_template:

                missing_names = ", ".join(
                    sorted(
                        missing_from_template
                    )
                )

                raise ValueError(
                    "Required variables are not present in the "
                    f"template: {missing_names}"
                )

        self.prompts[
            normalized_name
        ] = {
            "name": normalized_name,
            "template": normalized_template,
            "description": str(
                description
            ).strip(),
            "version": normalized_version,
            "category": normalized_category,
            "required_variables": (
                normalized_required_variables
            ),
            "created_at": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
        }

    # ==========================================================
    # Retrieval
    # ==========================================================

    def get_prompt(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """
        Return a copy of prompt metadata.
        """

        normalized_name = str(
            name
        ).strip()

        prompt = self.prompts.get(
            normalized_name
        )

        if prompt is None:

            return None

        return deepcopy(
            prompt
        )

    def get_template(
        self,
        name: str,
    ) -> str:
        """
        Return only the prompt template.
        """

        prompt = self.get_prompt(
            name
        )

        if prompt is None:

            raise KeyError(
                f"Prompt '{name}' not found."
            )

        return str(
            prompt["template"]
        )

    def get_required_variables(
        self,
        name: str,
    ) -> tuple[str, ...]:
        """
        Return required variables for one prompt.
        """

        prompt = self.get_prompt(
            name
        )

        if prompt is None:

            raise KeyError(
                f"Prompt '{name}' not found."
            )

        variables = prompt.get(
            "required_variables",
            (),
        )

        return tuple(
            str(
                variable
            )
            for variable in variables
        )

    def has_prompt(
        self,
        name: str,
    ) -> bool:
        """
        Return whether a prompt is registered.
        """

        return str(
            name
        ).strip() in self.prompts

    # ==========================================================
    # Rendering
    # ==========================================================

    def render_prompt(
        self,
        name: str,
        variables: dict[str, Any] | None = None,
        **keyword_variables: Any,
    ) -> str:
        """
        Render a registered prompt.

        Variables can be supplied through a dictionary, keyword
        arguments, or both. Keyword arguments override dictionary
        values.
        """

        prompt = self.get_prompt(
            name
        )

        if prompt is None:

            raise KeyError(
                f"Prompt '{name}' not found."
            )

        render_variables: dict[
            str,
            Any,
        ] = {}

        if variables is not None:

            if not isinstance(
                variables,
                dict,
            ):

                raise TypeError(
                    "variables must be a dictionary or None."
                )

            render_variables.update(
                variables
            )

        render_variables.update(
            keyword_variables
        )

        required_variables = tuple(
            prompt.get(
                "required_variables",
                (),
            )
        )

        missing_variables = [
            variable
            for variable in required_variables
            if variable not in render_variables
        ]

        if missing_variables:

            missing_names = ", ".join(
                missing_variables
            )

            raise ValueError(
                f"Missing prompt variables: {missing_names}"
            )

        normalized_variables = {
            key: self._format_variable(
                value
            )
            for key, value in (
                render_variables.items()
            )
        }

        template = str(
            prompt["template"]
        )

        try:

            return template.format(
                **normalized_variables
            )

        except KeyError as error:

            missing_variable = str(
                error
            ).strip(
                "'"
            )

            raise ValueError(
                "Prompt variable is missing: "
                f"{missing_variable}"
            ) from error

        except (
            IndexError,
            ValueError,
        ) as error:

            raise ValueError(
                f"Prompt '{name}' could not be rendered."
            ) from error

    # ==========================================================
    # Management
    # ==========================================================

    def list_prompts(
        self,
        category: str | None = None,
    ) -> list[str]:
        """
        Return registered prompt names.

        When category is provided, only prompts from that category
        are returned.
        """

        if category is None:

            return sorted(
                self.prompts.keys()
            )

        normalized_category = str(
            category
        ).strip().lower()

        return sorted(
            name
            for name, prompt in self.prompts.items()
            if str(
                prompt.get(
                    "category",
                    "",
                )
            ).casefold()
            == normalized_category.casefold()
        )

    def list_categories(
        self,
    ) -> list[str]:
        """
        Return available prompt categories.
        """

        return sorted(
            {
                str(
                    prompt.get(
                        "category",
                        "general",
                    )
                )
                for prompt in self.prompts.values()
            }
        )

    def remove_prompt(
        self,
        name: str,
    ) -> bool:
        """
        Remove a registered prompt.
        """

        normalized_name = str(
            name
        ).strip()

        if normalized_name not in self.prompts:

            return False

        del self.prompts[
            normalized_name
        ]

        return True

    def clear(
        self,
    ) -> None:
        """
        Remove all registered prompts.
        """

        self.prompts.clear()

    def reload_defaults(
        self,
    ) -> None:
        """
        Replace current registry with default prompts.
        """

        self.clear()
        self._load_default_prompts()

    # ==========================================================
    # Metadata
    # ==========================================================

    def metadata(
        self,
    ) -> dict[str, Any]:
        """
        Return prompt-manager information.
        """

        return {
            "total_prompts": len(
                self.prompts
            ),
            "categories": (
                self.list_categories()
            ),
            "prompts": (
                self.list_prompts()
            ),
        }

    # ==========================================================
    # Default prompts
    # ==========================================================

    def _load_default_prompts(
        self,
    ) -> None:
        """
        Register built-in investigation prompts.
        """

        self._register_message_prompts()
        self._register_conversation_prompts()
        self._register_entity_prompts()
        self._register_relationship_prompts()
        self._register_timeline_prompts()
        self._register_investigation_prompts()
        self._register_reporting_prompts()

    def _register_message_prompts(
        self,
    ) -> None:
        """
        Register prompts for individual messages.
        """

        self.register_prompt(
            name="message_analysis",
            category="messages",
            version="2.1",
            description=(
                "Analyze one investigation message and return "
                "evidence-oriented findings."
            ),
            template=(
                "You are an investigation analysis assistant.\n\n"

                "Analyze the message using only the information "
                "provided below. Do not invent facts, identities, "
                "motives or relationships.\n\n"

                "LANGUAGE RULE:\n"
                "Use the language of the selected message when it "
                "contains meaningful natural-language text. If the "
                "message does not make the language clear, use the "
                "language of the surrounding messages. Preserve "
                "names, usernames, URLs, identifiers and direct "
                "excerpts in their original form.\n\n"

                "INVESTIGATION:\n"
                "{case_context}\n\n"

                "SELECTED MESSAGE:\n"
                "{message}\n\n"

                "RELATED CONTEXT:\n"
                "{related_context}\n\n"

                "RESPONSE FORMAT:\n\n"

                "# Краткий вывод\n\n"
                "Give the main conclusion in 2 to 5 sentences.\n\n"

                "# Подтверждённые факты\n\n"
                "List only facts directly supported by the supplied "
                "message or investigation context.\n\n"

                "# Анализ\n\n"
                "Explain the possible meaning and investigative "
                "relevance. Clearly mark every interpretation as an "
                "interpretation rather than a confirmed fact.\n\n"

                "# Связанные данные\n\n"
                "Organize relevant messages, entities, evidence, "
                "relationships and timeline events into short "
                "subsections. Omit categories that contain nothing "
                "relevant.\n\n"

                "# Неопределённость\n\n"
                "Describe missing context, alternative explanations "
                "and limits of the analysis.\n\n"

                "# Рекомендуемые следующие шаги\n\n"
                "Suggest prioritized, lawful verification steps only "
                "when useful.\n\n"

                "STYLE RULES:\n"
                "- Use Markdown headings.\n"
                "- Use short paragraphs.\n"
                "- Use bullet lists for multiple facts.\n"
                "- Do not produce one large paragraph.\n"
                "- Do not repeat the same information.\n"
                "- Distinguish facts from interpretations.\n"
                "- State clearly when data is insufficient."
            ),
        )

        self.register_prompt(
            name="message_risk_assessment",
            category="messages",
            version="2.0",
            description=(
                "Assess investigative relevance and possible risk "
                "signals in one message."
            ),
            template=(
                "Review the following message as an investigation "
                "analyst.\n\n"
                "MESSAGE:\n"
                "{message}\n\n"
                "CONTEXT:\n"
                "{context}\n\n"
                "Identify observable risk indicators, unusual "
                "patterns, urgency, contradictions and important "
                "unknowns. Do not make accusations or treat weak "
                "signals as proven facts.\n\n"
                "Return:\n"
                "- Observed indicators\n"
                "- Possible interpretations\n"
                "- Confidence and limitations\n"
                "- Recommended verification steps"
            ),
        )

        self.register_prompt(
            name="message_entity_extraction",
            category="messages",
            version="2.0",
            description=(
                "Extract candidate entities from one message."
            ),
            template=(
                "Extract candidate entities from the following "
                "message.\n\n"
                "MESSAGE:\n"
                "{message}\n\n"
                "Return candidates grouped by type:\n"
                "- person\n"
                "- organization\n"
                "- username or account\n"
                "- email\n"
                "- phone\n"
                "- domain or URL\n"
                "- location or address\n"
                "- document or identifier\n"
                "- other\n\n"
                "For every candidate include the exact text, "
                "suggested type, confidence and a brief reason. "
                "Do not invent values."
            ),
        )

    def _register_conversation_prompts(
        self,
    ) -> None:
        """
        Register prompts for groups of messages.
        """

        self.register_prompt(
            name="conversation_summary",
            category="conversations",
            version="2.0",
            description=(
                "Summarize a selected conversation or message set."
            ),
            template=(
                "Summarize the following investigation messages.\n\n"
                "CASE CONTEXT:\n"
                "{case_context}\n\n"
                "MESSAGES:\n"
                "{messages}\n\n"
                "Return:\n"
                "1. Chronological summary\n"
                "2. Main participants\n"
                "3. Main topics and decisions\n"
                "4. Important claims or contradictions\n"
                "5. Unresolved questions\n"
                "6. Potentially relevant evidence\n\n"
                "Use only the supplied material."
            ),
        )

        self.register_prompt(
            name="conversation_pattern_analysis",
            category="conversations",
            version="2.0",
            description=(
                "Identify communication and behavioural patterns."
            ),
            template=(
                "Analyze communication patterns in the selected "
                "messages.\n\n"
                "MESSAGES:\n"
                "{messages}\n\n"
                "AVAILABLE PARTICIPANT CONTEXT:\n"
                "{participant_context}\n\n"
                "Examine frequency, timing, recurring topics, "
                "changes in tone, coordination, avoidance, "
                "contradictions and other observable patterns.\n\n"
                "Do not diagnose people or infer hidden motives as "
                "facts. Separate observations, interpretations and "
                "uncertainties."
            ),
        )

        self.register_prompt(
            name="suspicious_activity_analysis",
            category="conversations",
            version="2.0",
            description=(
                "Review messages for potentially relevant unusual "
                "activity without presenting suspicion as proof."
            ),
            template=(
                "Review the following messages for unusual or "
                "investigatively relevant activity.\n\n"
                "MESSAGES:\n"
                "{messages}\n\n"
                "CASE CONTEXT:\n"
                "{case_context}\n\n"
                "Identify:\n"
                "- unusual timing or coordination\n"
                "- repeated or coded-looking language\n"
                "- contradictions\n"
                "- references to locations, accounts or documents\n"
                "- missing context that should be verified\n\n"
                "Do not claim criminality or intent. State the "
                "evidence supporting each observation and provide "
                "alternative explanations where reasonable."
            ),
        )

    def _register_entity_prompts(
        self,
    ) -> None:
        """
        Register prompts for entity analysis.
        """

        self.register_prompt(
            name="entity_analysis",
            category="entities",
            version="2.0",
            description=(
                "Analyze one entity using available investigation "
                "context."
            ),
            template=(
                "Analyze the following investigation entity.\n\n"
                "ENTITY:\n"
                "{entity}\n\n"
                "RELATED MESSAGES:\n"
                "{messages}\n\n"
                "RELATED EVIDENCE:\n"
                "{evidence}\n\n"
                "KNOWN RELATIONSHIPS:\n"
                "{relationships}\n\n"
                "Return:\n"
                "1. Verified attributes\n"
                "2. Associated identifiers\n"
                "3. Relevant communications and evidence\n"
                "4. Known relationships\n"
                "5. Possible duplicate identities\n"
                "6. Gaps and recommended verification steps\n\n"
                "Do not merge identities without sufficient support."
            ),
        )

        self.register_prompt(
            name="entity_comparison",
            category="entities",
            version="2.0",
            description=(
                "Compare two entities for possible identity overlap."
            ),
            template=(
                "Compare the following two investigation entities.\n\n"
                "ENTITY A:\n"
                "{entity_a}\n\n"
                "ENTITY B:\n"
                "{entity_b}\n\n"
                "SUPPORTING CONTEXT:\n"
                "{context}\n\n"
                "Assess similarities, differences, shared "
                "identifiers, contradictory details and the strength "
                "of evidence that they represent the same subject.\n\n"
                "Return a confidence assessment but do not treat it "
                "as a confirmed identity merge."
            ),
        )

    def _register_relationship_prompts(
        self,
    ) -> None:
        """
        Register prompts for relationship analysis.
        """

        self.register_prompt(
            name="relationship_analysis",
            category="relationships",
            version="2.0",
            description=(
                "Analyze relationships between investigation "
                "entities."
            ),
            template=(
                "Analyze the supplied investigation relationships.\n\n"
                "ENTITIES:\n"
                "{entities}\n\n"
                "RELATIONSHIPS:\n"
                "{relationships}\n\n"
                "SUPPORTING MESSAGES AND EVIDENCE:\n"
                "{supporting_context}\n\n"
                "Identify:\n"
                "1. Direct supported relationships\n"
                "2. Indirect connection paths\n"
                "3. Central or highly connected entities\n"
                "4. Conflicting or weakly supported links\n"
                "5. Missing links worth investigating\n\n"
                "Distinguish database facts from AI inferences."
            ),
        )

        self.register_prompt(
            name="network_hypothesis",
            category="relationships",
            version="2.0",
            description=(
                "Generate testable hypotheses about an entity "
                "network."
            ),
            template=(
                "Generate cautious, testable hypotheses about the "
                "following relationship network.\n\n"
                "NETWORK CONTEXT:\n"
                "{network_context}\n\n"
                "For each hypothesis provide:\n"
                "- hypothesis\n"
                "- supporting observations\n"
                "- contradicting or missing evidence\n"
                "- confidence level\n"
                "- lawful verification steps\n\n"
                "Do not present hypotheses as established facts."
            ),
        )

    def _register_timeline_prompts(
        self,
    ) -> None:
        """
        Register prompts for chronology analysis.
        """

        self.register_prompt(
            name="timeline_analysis",
            category="timeline",
            version="2.0",
            description=(
                "Analyze investigation chronology and event links."
            ),
            template=(
                "Analyze the following investigation timeline.\n\n"
                "TIMELINE EVENTS:\n"
                "{timeline}\n\n"
                "RELATED ENTITIES:\n"
                "{entities}\n\n"
                "RELATED MESSAGES AND EVIDENCE:\n"
                "{supporting_context}\n\n"
                "Return:\n"
                "1. Chronological narrative\n"
                "2. Key turning points\n"
                "3. Events that may be connected\n"
                "4. Contradictions or impossible sequences\n"
                "5. Significant gaps in time\n"
                "6. Recommended events or records to verify\n\n"
                "Separate direct evidence from inferred connections."
            ),
        )

        self.register_prompt(
            name="event_analysis",
            category="timeline",
            version="2.0",
            description=(
                "Analyze one timeline event in context."
            ),
            template=(
                "Analyze the selected timeline event.\n\n"
                "EVENT:\n"
                "{event}\n\n"
                "PRECEDING EVENTS:\n"
                "{preceding_events}\n\n"
                "FOLLOWING EVENTS:\n"
                "{following_events}\n\n"
                "RELATED CONTEXT:\n"
                "{related_context}\n\n"
                "Explain the event's verified significance, possible "
                "connections, uncertainty and recommended checks."
            ),
        )

    def _register_investigation_prompts(
        self,
    ) -> None:
        """
        Register complete-investigation prompts.
        """

        self.register_prompt(
            name="investigation_summary",
            category="investigation",
            version="2.0",
            description=(
                "Generate a structured summary of the entire case."
            ),
            template=(
                "Create a structured investigation summary from the "
                "following context.\n\n"
                "CASE:\n"
                "{case}\n\n"
                "MESSAGES:\n"
                "{messages}\n\n"
                "EVIDENCE:\n"
                "{evidence}\n\n"
                "ENTITIES:\n"
                "{entities}\n\n"
                "RELATIONSHIPS:\n"
                "{relationships}\n\n"
                "TIMELINE:\n"
                "{timeline}\n\n"
                "Return:\n"
                "1. Executive summary\n"
                "2. Confirmed facts\n"
                "3. Key entities and relationships\n"
                "4. Important chronology\n"
                "5. Major evidence\n"
                "6. Contradictions and uncertainties\n"
                "7. Open questions\n"
                "8. Recommended lawful next steps\n\n"
                "Do not add facts that are absent from the context."
            ),
        )

        self.register_prompt(
            name="investigation_chat",
            category="investigation",
            version="3.0",
            description=(
                "Answer a user question using the active "
                "investigation workspace with a clear and "
                "evidence-oriented structure."
            ),
            template=(
                "You are an investigation analysis assistant.\n\n"

                "Answer the user's question using only the supplied "
                "investigation material and retrieved knowledge. "
                "Do not invent facts, identities, motives, events, "
                "relationships, quotations or evidence.\n\n"

                "LANGUAGE RULE:\n"
                "Detect the language of the USER QUESTION and write "
                "the entire response in that same language. Do not "
                "choose the response language from the investigation "
                "data, retrieved context, interface language or "
                "system labels. Preserve names, usernames, URLs, "
                "identifiers and direct excerpts in their original "
                "form. If the user explicitly requests another "
                "response language, follow that request instead.\n\n"

                "ANALYSIS RULES:\n"
                "Before writing the answer, internally identify the "
                "relevant investigation facts, separate confirmed "
                "information from interpretation, check for "
                "contradictions and identify missing evidence. Do "
                "not expose private internal reasoning or hidden "
                "step-by-step deliberation. Present only a concise, "
                "clear and supported final analysis.\n\n"

                "Treat the supplied workspace as an intelligence "
                "case. Internally organize relevant information into "
                "persons, organizations, accounts, usernames, phone "
                "numbers, emails, domains, locations, events, "
                "messages, relationships, evidence, timeline items "
                "and open questions. Do not output irrelevant "
                "categories.\n\n"

                "ACTIVE INVESTIGATION:\n"
                "{workspace_context}\n\n"

                "RETRIEVED KNOWLEDGE:\n"
                "{retrieved_context}\n\n"

                "RECENT CONVERSATION:\n"
                "{conversation_history}\n\n"

                "USER QUESTION:\n"
                "{question}\n\n"

                "RESPONSE FORMAT (MANDATORY):\n\n"

                "Start directly with the answer. Do not begin with "
                "generic phrases such as \"I analyzed the data\", "
                "\"Based on the information provided\" or "
                "\"Here is the analysis\".\n\n"

                "# Краткий ответ\n\n"
                "Answer the user's main question in 2 to 5 clear "
                "sentences. Include the most important conclusion "
                "first. If the available information is insufficient, "
                "state that immediately.\n\n"

                "# Что подтверждено данными\n\n"
                "List only facts directly supported by the supplied "
                "investigation. Use concise bullet points. For each "
                "important fact, identify the supporting source type, "
                "such as a message, entity, evidence item, "
                "relationship, timeline event or report. Refer to "
                "available identifiers, dates, participants or titles "
                "when they help distinguish the source.\n\n"

                "# Анализ\n\n"
                "Explain the significance of the confirmed facts. "
                "Separate different ideas into short subsections. "
                "Clearly label interpretations, patterns and possible "
                "explanations. Never present an interpretation as a "
                "confirmed fact.\n\n"

                "# Возможные выводы\n\n"
                "Present only conclusions relevant to the user's "
                "question. For each conclusion use this format:\n"
                "- Conclusion\n"
                "- Confidence: high, medium or low\n"
                "- Supporting information\n"
                "- Limitations or alternative explanation\n\n"
                "Do not include this section when no reasonable "
                "conclusion can be supported.\n\n"

                "# Противоречия и неопределённость\n\n"
                "List contradictions, ambiguous information, weak "
                "links and possible alternative explanations. State "
                "what cannot be determined from the current data. "
                "Do not imply deception, guilt or intent without "
                "direct supporting evidence.\n\n"

                "# Недостающая информация\n\n"
                "List the specific information needed to answer the "
                "question more confidently. Do not use generic "
                "phrases such as \"more data is needed\" without "
                "explaining which data is missing.\n\n"

                "# Следующие шаги\n\n"
                "Suggest a short prioritized list of lawful and "
                "proportionate verification steps. For each step "
                "state its purpose and expected evidentiary value. "
                "Do not recommend credential theft, unauthorized "
                "access, impersonation, harassment, intrusion or "
                "other unlawful actions. Omit this section when no "
                "next steps are relevant.\n\n"

                "ADAPTIVE STRUCTURE RULE:\n"
                "The headings above define the preferred analytical "
                "structure, but do not include empty or irrelevant "
                "sections. For a simple factual question, use only "
                "\"Краткий ответ\" and the minimum supporting facts. "
                "For a complex analytical question, use all relevant "
                "sections. Translate every heading into the language "
                "required by the LANGUAGE RULE.\n\n"

                "WRITING STYLE:\n"
                "- Use Markdown headings and bullet lists.\n"
                "- Use short paragraphs of no more than 3 to 5 "
                "sentences.\n"
                "- Never produce one large unbroken paragraph.\n"
                "- Do not mix unrelated facts in one paragraph.\n"
                "- Put the most relevant information first.\n"
                "- Do not repeat the same fact in several sections.\n"
                "- Distinguish facts, source claims and analytical "
                "interpretations.\n"
                "- Prefer precise language over dramatic language.\n"
                "- Do not use excessive disclaimers.\n"
                "- Do not overload the answer with irrelevant "
                "workspace data.\n"
                "- Do not create tables unless comparison is central "
                "to the user's question.\n"
                "- Keep identifiers and dates exact when they are "
                "available.\n"
                "- Explicitly state when the supplied information is "
                "insufficient.\n"
                "- The final response must follow the LANGUAGE RULE."
            ),
        )

        self.register_prompt(
            name="hypothesis_generation",
            category="investigation",
            version="2.0",
            description=(
                "Generate cautious and testable investigation "
                "hypotheses."
            ),
            template=(
                "Using only the supplied investigation context, "
                "generate a limited set of testable hypotheses.\n\n"
                "CONTEXT:\n"
                "{context}\n\n"
                "For each hypothesis provide:\n"
                "- statement\n"
                "- supporting evidence\n"
                "- contradictory evidence\n"
                "- confidence\n"
                "- information needed to test it\n\n"
                "Do not present hypotheses as facts and do not infer "
                "protected or sensitive personal attributes."
            ),
        )

        self.register_prompt(
            name="next_investigation_steps",
            category="investigation",
            version="2.0",
            description=(
                "Recommend lawful and evidence-oriented next steps."
            ),
            template=(
                "Review the current investigation state.\n\n"
                "CURRENT CONTEXT:\n"
                "{context}\n\n"
                "Recommend prioritized next steps that are lawful, "
                "proportionate and based on identifiable gaps.\n\n"
                "For every recommendation include:\n"
                "- objective\n"
                "- reason\n"
                "- required data or source\n"
                "- expected evidentiary value\n"
                "- limitations or risks\n\n"
                "Do not recommend intrusion, credential theft, "
                "impersonation, harassment or unlawful access."
            ),
        )

        self.register_prompt(
            name="contradiction_analysis",
            category="investigation",
            version="2.0",
            description=(
                "Find conflicting claims and inconsistent records."
            ),
            template=(
                "Identify contradictions and inconsistencies in the "
                "following investigation context.\n\n"
                "CONTEXT:\n"
                "{context}\n\n"
                "For each contradiction provide:\n"
                "- conflicting statements or records\n"
                "- involved sources\n"
                "- possible non-malicious explanations\n"
                "- what evidence could resolve the conflict\n\n"
                "Do not assume deception without supporting evidence."
            ),
        )

    def _register_reporting_prompts(
        self,
    ) -> None:
        """
        Register prompts for AI-assisted reporting.
        """

        self.register_prompt(
            name="investigation_report",
            category="reports",
            version="2.0",
            description=(
                "Generate a formal investigation report draft."
            ),
            template=(
                "Prepare a professional investigation report draft "
                "from the supplied context.\n\n"
                "INVESTIGATION CONTEXT:\n"
                "{context}\n\n"
                "REPORT REQUIREMENTS:\n"
                "{requirements}\n\n"
                "Use these sections:\n"
                "1. Scope\n"
                "2. Methodology\n"
                "3. Sources reviewed\n"
                "4. Findings\n"
                "5. Entity and relationship overview\n"
                "6. Timeline\n"
                "7. Limitations\n"
                "8. Conclusions\n"
                "9. Recommended next steps\n\n"
                "Distinguish confirmed facts, source claims and "
                "analytical inferences."
            ),
        )

        self.register_prompt(
            name="executive_brief",
            category="reports",
            version="2.0",
            description=(
                "Generate a concise decision-maker briefing."
            ),
            template=(
                "Create a concise executive briefing from the "
                "following investigation material.\n\n"
                "CONTEXT:\n"
                "{context}\n\n"
                "Include:\n"
                "- objective\n"
                "- most important findings\n"
                "- key entities\n"
                "- immediate risks or concerns\n"
                "- important uncertainties\n"
                "- recommended next actions\n\n"
                "Keep the briefing factual and clearly label "
                "analytical judgments."
            ),
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def _normalize_identifier(
        value: str,
        *,
        field_name: str,
    ) -> str:
        """
        Normalize prompt and category identifiers.
        """

        normalized_value = str(
            value
        ).strip().lower()

        if not normalized_value:

            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized_value

    def _extract_template_variables(
        self,
        template: str,
    ) -> tuple[str, ...]:
        """
        Extract unique named variables from a format template.
        """

        variables: list[str] = []

        for (
            _,
            field_name,
            _,
            _,
        ) in self._formatter.parse(
            template
        ):

            if not field_name:

                continue

            base_name = (
                field_name
                .split(
                    ".",
                    1,
                )[0]
                .split(
                    "[",
                    1,
                )[0]
            )

            if (
                base_name
                and base_name not in variables
            ):

                variables.append(
                    base_name
                )

        return tuple(
            variables
        )

    @staticmethod
    def _format_variable(
        value: Any,
    ) -> str:
        """
        Convert prompt variables to readable text.
        """

        if value is None:

            return "Not available"

        if isinstance(
            value,
            str,
        ):

            normalized_value = value.strip()

            return (
                normalized_value
                if normalized_value
                else "Not available"
            )

        if isinstance(
            value,
            dict,
        ):

            if not value:

                return "Not available"

            lines: list[str] = []

            for key, item in value.items():

                readable_key = (
                    str(
                        key
                    )
                    .replace(
                        "_",
                        " ",
                    )
                    .strip()
                    .title()
                )

                lines.append(
                    f"{readable_key}: "
                    f"{PromptManager._format_variable(item)}"
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

            if not value:

                return "Not available"

            return "\n\n".join(
                (
                    f"[{index}] "
                    f"{PromptManager._format_variable(item)}"
                )
                for index, item in enumerate(
                    value,
                    start=1,
                )
            )

        return str(
            value
        )