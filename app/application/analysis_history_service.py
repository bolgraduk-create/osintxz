"""Persistent Analysis Workspace history backed by the existing AIAnalysis table."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_analysis import AnalysisType
from app.repositories.ai_analysis_repository import AIAnalysisRepository


HISTORY_MARKER = "analysis_workspace_history"
HISTORY_VERSION = "R13.28c"


class AnalysisHistoryService:
    """Persist compact UI analysis snapshots separately from Evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AIAnalysisRepository(session)

    def save(
        self,
        *,
        case_id: str | UUID,
        snapshot: dict[str, Any],
    ) -> str:
        case_uuid = (
            case_id
            if isinstance(case_id, UUID)
            else UUID(str(case_id))
        )
        safe_snapshot = self._safe_snapshot(snapshot)

        model_info = dict(safe_snapshot.get("modelInfo") or {})
        run_config = dict(safe_snapshot.get("runConfig") or {})
        model_name = str(
            run_config.get("model")
            or model_info.get("model")
            or ""
        ).strip() or None

        summary = str(safe_snapshot.get("summary") or "").strip()
        result_text = summary or "Analysis Workspace run"

        metadata = {
            "kind": HISTORY_MARKER,
            "version": HISTORY_VERSION,
            "snapshot": safe_snapshot,
        }

        row = self.repository.create(
            case_id=case_uuid,
            analysis_type=AnalysisType.OTHER,
            model_name=model_name,
            result=result_text,
            confidence=None,
            metadata_json=json.dumps(
                metadata,
                ensure_ascii=False,
                default=str,
            ),
        )
        self.session.flush()
        return str(row.id)

    def list_for_case(
        self,
        case_id: str | UUID,
        *,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        case_uuid = (
            case_id
            if isinstance(case_id, UUID)
            else UUID(str(case_id))
        )

        rows = self.repository.get_by_case(case_uuid)
        history: list[dict[str, Any]] = []

        for row in rows:
            if len(history) >= max(1, min(int(limit), 100)):
                break

            payload = self._metadata(row.metadata_json)
            if payload.get("kind") != HISTORY_MARKER:
                continue

            snapshot = payload.get("snapshot")
            if not isinstance(snapshot, dict):
                continue

            item = dict(snapshot)
            item["historyId"] = str(row.id)
            item["historyCreatedAt"] = (
                row.created_at.isoformat()
                if row.created_at is not None
                else ""
            )
            item["historyModel"] = str(row.model_name or "")
            history.append(item)

        return history

    @staticmethod
    def _metadata(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}

    @staticmethod
    def _safe_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        """Store the analytical result, never provider secrets or raw RAG text."""

        source_rows = [
            dict(item)
            for item in list(snapshot.get("sources") or [])[:30]
            if isinstance(item, dict)
        ]
        conclusion_rows = [
            dict(item)
            for item in list(snapshot.get("conclusions") or [])
            if isinstance(item, dict)
        ]
        stage_rows = [
            dict(item)
            for item in list(snapshot.get("stages") or [])
            if isinstance(item, dict)
        ]

        provider = dict(snapshot.get("provider") or {})
        for key in (
            "api_key",
            "apiKey",
            "key",
            "token",
            "secret",
        ):
            provider.pop(key, None)

        return {
            "hasRun": True,
            "status": str(snapshot.get("status") or ""),
            "phase": "history",
            "caseId": str(snapshot.get("caseId") or ""),
            "question": str(snapshot.get("question") or ""),
            "scope": dict(snapshot.get("scope") or {}),
            "runConfig": dict(snapshot.get("runConfig") or {}),
            "summary": str(snapshot.get("summary") or ""),
            "summarySourceReferences": list(
                snapshot.get("summarySourceReferences") or []
            ),
            "conclusions": conclusion_rows,
            "facts": [
                dict(item)
                for item in list(snapshot.get("facts") or [])
                if isinstance(item, dict)
            ],
            "sources": source_rows,
            "stages": stage_rows,
            "warnings": list(snapshot.get("warnings") or []),
            "citationSummary": dict(
                snapshot.get("citationSummary") or {}
            ),
            "modelInfo": dict(snapshot.get("modelInfo") or {}),
            "provider": provider,
            "usage": dict(snapshot.get("usage") or {}),
            "cost": dict(snapshot.get("cost") or {}),
            "successfulStages": int(
                snapshot.get("successfulStages") or 0
            ),
            "failedStages": int(snapshot.get("failedStages") or 0),
            "skippedStages": int(snapshot.get("skippedStages") or 0),
            "cancelledStages": int(
                snapshot.get("cancelledStages") or 0
            ),
            "durationSeconds": float(
                snapshot.get("durationSeconds") or 0.0
            ),
            "durationText": str(snapshot.get("durationText") or ""),
            "generatedAt": str(snapshot.get("generatedAt") or ""),
            "notice": str(snapshot.get("notice") or ""),
        }


__all__ = [
    "AnalysisHistoryService",
    "HISTORY_MARKER",
    "HISTORY_VERSION",
]
