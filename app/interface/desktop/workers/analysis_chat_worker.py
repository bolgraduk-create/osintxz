from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.analysis_chat_history_service import (
    AnalysisChatHistoryService,
)
from app.application.analysis_run_profile import (
    estimate_openai_cost,
    generation_kwargs_for_profile,
    normalize_analysis_mode,
)
from app.security.sensitive_content import sanitized_text


class AnalysisChatWorker(QObject):
    """Execute one conversational Analysis turn in a worker thread."""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        case_id: str,
        session_id: str,
        message: str,
        conversation: list[dict[str, Any]],
        analysis_context: dict[str, Any],
        provider_name: str,
        model: str,
        reasoning_effort: str,
        mode: str,
        scope_type: str,
        focus_entity_id: str,
        focus_entity_label: str,
    ) -> None:
        super().__init__()
        self.case_id = str(case_id or "").strip()
        self.session_id = str(session_id or "").strip()
        self.message = str(message or "").strip()
        self.conversation = [
            dict(item)
            for item in list(conversation or [])
            if isinstance(item, dict)
        ]
        self.analysis_context = (
            dict(analysis_context)
            if isinstance(analysis_context, dict)
            else {}
        )
        self.provider_name = str(provider_name or "").strip().casefold()
        self.model = str(model or "").strip()
        self.reasoning_effort = str(reasoning_effort or "").strip().casefold()
        self.mode = str(mode or "standard").strip().casefold()
        self.scope_type = str(scope_type or "case").strip().casefold()
        self.focus_entity_id = str(focus_entity_id or "").strip()
        self.focus_entity_label = str(focus_entity_label or "").strip()

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        session = None
        container = None

        try:
            case_uuid = UUID(self.case_id)
            if not self.message:
                raise ValueError("Chat message cannot be empty.")

            profile = normalize_analysis_mode(self.mode)
            session = create_session()
            container = ServiceContainer(
                session,
                ai_provider_name=self.provider_name or None,
                ai_model_name=self.model or None,
                ai_reasoning_effort=self.reasoning_effort or None,
            )

            provider_name = str(
                container.ai_manager.provider_name or ""
            ).strip().casefold()
            selected_model = str(
                container.ai_manager.model_name or self.model
            ).strip()
            selected_reasoning = (
                self.reasoning_effort
                if provider_name == "openai"
                else ""
            )

            generation_kwargs = generation_kwargs_for_profile(
                provider=provider_name,
                mode=profile.key,
                model=selected_model or None,
                reasoning_effort=selected_reasoning or None,
            )

            result = container.analysis_chat_service.reply(
                case_id=case_uuid,
                message=self.message,
                conversation=self.conversation,
                analysis_context=self.analysis_context,
                scope_type=self.scope_type,
                focus_entity_id=self.focus_entity_id,
                focus_entity_label=self.focus_entity_label,
                generation_kwargs=generation_kwargs,
            )

            usage = dict(container.ai_manager.usage_snapshot() or {})
            cost = (
                estimate_openai_cost(usage)
                if provider_name == "openai"
                else {
                    "currency": "",
                    "estimatedUsd": 0.0,
                    "display": "Local",
                    "pricedRequests": 0,
                    "unpricedRequests": 0,
                    "pricingEffectiveDate": "",
                    "approximate": False,
                    "notice": "Local provider usage is not billed by OpenAI.",
                }
            )

            scope = {
                "type": (
                    "person"
                    if (
                        self.scope_type == "person"
                        and self.focus_entity_id
                        and self.focus_entity_label
                    )
                    else "case"
                ),
                "entityId": (
                    self.focus_entity_id
                    if self.scope_type == "person"
                    else ""
                ),
                "label": (
                    self.focus_entity_label
                    if (
                        self.scope_type == "person"
                        and self.focus_entity_label
                    )
                    else "Entire Investigation"
                ),
            }

            payload = {
                "sessionId": self.session_id,
                "role": "assistant",
                "text": result.assistant_message,
                "provider": provider_name,
                "model": selected_model,
                "reasoningEffort": selected_reasoning,
                "scope": scope,
                "sourceReferences": list(result.source_references),
                "invalidSourceReferences": list(
                    result.invalid_source_references
                ),
                "sources": [
                    dict(item)
                    for item in result.sources
                ],
                "warnings": list(result.warnings),
                "usage": usage,
                "cost": cost,
                "metadata": dict(result.metadata),
                "durationSeconds": round(perf_counter() - started, 3),
            }

            # Keep the read-side Analysis turn transaction read-only.
            container.rollback()

            history_session = None
            try:
                history_session = create_session()
                history = AnalysisChatHistoryService(history_session)
                turn_id = history.save_turn(
                    case_id=self.case_id,
                    session_id=self.session_id,
                    user_message=result.user_message,
                    assistant_message=result.assistant_message,
                    provider=provider_name,
                    model=selected_model,
                    reasoning_effort=selected_reasoning,
                    scope=scope,
                    source_references=list(result.source_references),
                    sources=[dict(item) for item in result.sources],
                    usage=usage,
                    cost=cost,
                    warnings=list(result.warnings),
                )
                history_session.commit()
                payload["turnId"] = turn_id
                payload["historyPersisted"] = True
            except Exception as history_exc:
                if history_session is not None:
                    try:
                        history_session.rollback()
                    except Exception:
                        pass
                payload["historyPersisted"] = False
                payload["warnings"].append(
                    "Chat reply completed, but history could not be saved: "
                    + sanitized_text(history_exc)
                )
            finally:
                if history_session is not None:
                    try:
                        history_session.close()
                    except Exception:
                        pass

            self.succeeded.emit(payload)
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass

            self.failed.emit(
                {
                    "error": sanitized_text(exc),
                    "sessionId": self.session_id,
                    "durationSeconds": round(perf_counter() - started, 3),
                }
            )
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass
