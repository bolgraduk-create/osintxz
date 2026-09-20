"""R13.23.1 analyst-selected corroborating mention -> PERSON association.

This service persists a review decision without claiming that the source proves
identity.  It reuses the existing Source/Evidence/EvidenceEntity model and does
not add database tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit

from app.models.entity import EntityType
from app.models.evidence import EvidenceType
from app.models.source import SourceType


@dataclass(slots=True)
class PersonMentionSelectionResult:
    evidence_id: str
    source_id: str
    duplicate: bool = False


class PersonMentionSelectionService:
    """Attach one safe, already-rendered corroborating mention to a PERSON."""

    MAX_SIGNALS = 8

    def __init__(
        self,
        *,
        source_service: Any,
        evidence_service: Any,
        evidence_link_service: Any,
    ) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.evidence_link_service = evidence_link_service

    def add(self, *, person: Any, mention: dict[str, Any]) -> PersonMentionSelectionResult:
        self._validate_person(person)
        safe = self._normalize_mention(mention)
        mention_key = self._mention_key(safe)
        person_id = getattr(person, "id")
        case_id = getattr(person, "case_id")

        duplicate = self._find_existing(person_id=person_id, mention_key=mention_key)
        if duplicate is not None:
            return PersonMentionSelectionResult(
                evidence_id=str(getattr(duplicate, "id", "") or ""),
                source_id=str(getattr(duplicate, "source_id", "") or ""),
                duplicate=True,
            )

        title = safe["title"]
        source_name = safe["source"] or "Corroborating mention"
        source = self.source_service.create_source(
            case_id=case_id,
            name=f"Mention · {source_name} · {title}"[:255],
            source_type=SourceType.OTHER,
            path=f"mention://person/{person_id}/{mention_key}",
            description=(
                "Analyst-selected corroborating mention from unified investigation search. "
                "Selection records relevance/provenance only and does not independently "
                "verify identity or ownership."
            ),
        )

        url = safe["url"]
        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=EvidenceType.LINK if url else EvidenceType.DOCUMENT,
            title=f"Corroborating mention · {title}"[:255],
            value=(url or title)[:1024],
            description=(
                "Analyst attached a multi-signal mention to this person profile. "
                "The mention is review/provenance evidence and is not proof that every "
                "statement in the source belongs to the person."
            ),
            metadata_json=json.dumps(
                {
                    "workflow": "person_mention_selection",
                    "association_basis": "analyst_selected_corroborating_mention",
                    "identity_verified": False,
                    "person_entity_id": str(person_id),
                    "mention_key": mention_key,
                    "mention": {
                        "title": title,
                        "url": url,
                        "source": safe["source"],
                        "detail": safe["detail"],
                        "summary": safe["summary"],
                        "score": safe["score"],
                        "signals": safe["signals"],
                        "lane": safe["lane"],
                        "status": safe["status"],
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        self._flush_evidence()
        self.evidence_link_service.ensure_link(
            evidence_id=evidence.id,
            entity_id=person_id,
        )
        return PersonMentionSelectionResult(
            evidence_id=str(evidence.id),
            source_id=str(source.id),
            duplicate=False,
        )

    def _find_existing(self, *, person_id: Any, mention_key: str) -> Any | None:
        try:
            rows = list(
                self.evidence_link_service.get_evidence_objects_for_entity(person_id)
                or []
            )
        except Exception:
            return None
        for evidence in rows:
            metadata = self._metadata_dict(getattr(evidence, "metadata_json", None))
            if (
                metadata.get("workflow") == "person_mention_selection"
                and str(metadata.get("mention_key") or "") == mention_key
            ):
                return evidence
        return None

    @classmethod
    def _normalize_mention(cls, mention: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(mention, dict):
            raise TypeError("Mention payload must be a dictionary.")

        title = cls._clean(mention.get("title"))
        source = cls._clean(mention.get("source"))
        detail = cls._clean(mention.get("detail"))
        summary = cls._clean(mention.get("mentionSummary") or mention.get("summary"))
        lane = cls._clean(mention.get("lane"))
        status = cls._clean(mention.get("mentionLabel") or mention.get("status"))
        url = cls._safe_http_url(mention.get("url"))

        raw_signals = mention.get("mentionSignals") or mention.get("signals") or []
        if isinstance(raw_signals, str):
            raw_signals = [raw_signals]
        signals: list[str] = []
        seen: set[str] = set()
        for value in list(raw_signals) if isinstance(raw_signals, (list, tuple, set, frozenset)) else []:
            text = cls._clean(value)
            key = text.casefold()
            if text and key not in seen:
                seen.add(key)
                signals.append(text)
            if len(signals) >= cls.MAX_SIGNALS:
                break

        try:
            score = max(0.0, min(100.0, float(mention.get("mentionScore") or mention.get("score") or 0.0)))
        except (TypeError, ValueError):
            score = 0.0

        if not title:
            raise ValueError("Corroborating mention title is required.")
        if len(signals) < 2:
            raise ValueError("A corroborating mention requires at least two matched signals.")

        return {
            "title": title[:255],
            "source": source[:255],
            "detail": detail[:2000],
            "summary": summary[:1000],
            "url": url,
            "score": round(score, 1),
            "signals": signals,
            "lane": lane[:80],
            "status": status[:120],
        }

    @staticmethod
    def _mention_key(mention: dict[str, Any]) -> str:
        material = "\n".join(
            [
                str(mention.get("url") or "").casefold(),
                str(mention.get("title") or "").casefold(),
                str(mention.get("source") or "").casefold(),
                "|".join(str(item).casefold() for item in mention.get("signals") or []),
            ]
        )
        return sha256(material.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _validate_person(person: Any) -> None:
        if person is None:
            raise ValueError("Person entity is required.")
        entity_type = getattr(
            getattr(person, "entity_type", None),
            "value",
            getattr(person, "entity_type", ""),
        )
        if str(entity_type) != EntityType.PERSON.value:
            raise ValueError("Corroborating mentions can only be attached to PERSON entities.")
        if getattr(person, "id", None) is None or getattr(person, "case_id", None) is None:
            raise ValueError("Person entity is incomplete.")

    def _flush_evidence(self) -> None:
        repository = getattr(self.evidence_service, "repository", None)
        session = getattr(repository, "session", None)
        if session is not None:
            session.flush()

    @staticmethod
    def _metadata_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _clean(value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    @staticmethod
    def _safe_http_url(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        try:
            parsed = urlsplit(text)
        except Exception:
            return ""
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return ""
        return text[:2048]
