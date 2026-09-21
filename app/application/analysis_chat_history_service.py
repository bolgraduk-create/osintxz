"""Persistent conversational Analysis chat history using the existing AIAnalysis table."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import AnalysisType
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.security.sensitive_content import sanitize_sensitive_value


CHAT_MARKER = "analysis_workspace_chat_turn"
CHAT_VERSION = "R13.28h"


class AnalysisChatHistoryService:
    """Persist assistant turns without introducing a new database table."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AIAnalysisRepository(session)

    def save_turn(
        self,
        *,
        case_id: str | UUID,
        session_id: str,
        user_message: str,
        assistant_message: str,
        provider: str,
        model: str,
        reasoning_effort: str,
        scope: dict[str, Any],
        source_references: list[str] | tuple[str, ...],
        sources: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        usage: dict[str, Any] | None = None,
        cost: dict[str, Any] | None = None,
        warnings: list[str] | tuple[str, ...] = (),
    ) -> str:
        case_uuid = case_id if isinstance(case_id, UUID) else UUID(str(case_id))
        safe = sanitize_sensitive_value(
            {
                "userMessage": user_message,
                "assistantMessage": assistant_message,
                "provider": provider,
                "model": model,
                "reasoningEffort": reasoning_effort,
                "scope": dict(scope or {}),
                "sourceReferences": list(source_references or []),
                "sources": [dict(item) for item in list(sources or [])[:20]],
                "usage": dict(usage or {}),
                "cost": dict(cost or {}),
                "warnings": list(warnings or []),
            }
        )
        if not isinstance(safe, dict):
            safe = {}

        metadata = {
            "kind": CHAT_MARKER,
            "version": CHAT_VERSION,
            "sessionId": str(session_id or ""),
            "turn": safe,
        }

        row = self.repository.create(
            case_id=case_uuid,
            analysis_type=AnalysisType.OTHER,
            model_name=str(model or "").strip()[:100] or None,
            result=str(safe.get("assistantMessage") or "Analysis chat response"),
            confidence=None,
            metadata_json=json.dumps(
                metadata,
                ensure_ascii=False,
                default=str,
            ),
        )
        self.session.flush()
        return str(row.id)

    def load_latest_session(
        self,
        case_id: str | UUID,
        *,
        limit_turns: int = 30,
    ) -> dict[str, Any]:
        case_uuid = case_id if isinstance(case_id, UUID) else UUID(str(case_id))
        rows = self.repository.get_by_case(case_uuid)

        latest_session = ""
        selected: list[tuple[Any, dict[str, Any]]] = []

        for row in rows:
            payload = self._metadata(row.metadata_json)
            if payload.get("kind") != CHAT_MARKER:
                continue

            session_id = str(payload.get("sessionId") or "")
            if not session_id:
                continue

            if not latest_session:
                latest_session = session_id
            if session_id != latest_session:
                continue

            turn = sanitize_sensitive_value(payload.get("turn"))
            if not isinstance(turn, dict):
                continue
            selected.append((row, turn))
            if len(selected) >= max(1, min(int(limit_turns), 100)):
                break

        selected.reverse()
        messages: list[dict[str, Any]] = []
        for row, turn in selected:
            created = (
                row.created_at.isoformat()
                if getattr(row, "created_at", None) is not None
                else ""
            )
            row_id = str(getattr(row, "id", "") or "")
            user_text = str(turn.get("userMessage") or "")
            assistant_text = str(turn.get("assistantMessage") or "")

            if user_text:
                messages.append(
                    {
                        "id": row_id + ":user",
                        "turnId": row_id,
                        "role": "user",
                        "text": user_text,
                        "createdAt": created,
                        "sourceReferences": [],
                        "sources": [],
                    }
                )
            if assistant_text:
                messages.append(
                    {
                        "id": row_id + ":assistant",
                        "turnId": row_id,
                        "role": "assistant",
                        "text": assistant_text,
                        "createdAt": created,
                        "provider": str(turn.get("provider") or ""),
                        "model": str(turn.get("model") or ""),
                        "reasoningEffort": str(
                            turn.get("reasoningEffort") or ""
                        ),
                        "scope": dict(turn.get("scope") or {}),
                        "sourceReferences": list(
                            turn.get("sourceReferences") or []
                        ),
                        "sources": [
                            dict(item)
                            for item in list(turn.get("sources") or [])
                            if isinstance(item, dict)
                        ],
                        "usage": dict(turn.get("usage") or {}),
                        "cost": dict(turn.get("cost") or {}),
                        "warnings": list(turn.get("warnings") or []),
                    }
                )

        return {
            "sessionId": latest_session,
            "messages": messages,
        }

    @staticmethod
    def _metadata(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            payload = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, dict) else {}


__all__ = [
    "AnalysisChatHistoryService",
    "CHAT_MARKER",
    "CHAT_VERSION",
]
