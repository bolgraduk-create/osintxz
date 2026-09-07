"""Lawful caller-ID boundary. Community labels never establish ownership.

Only explicit case-scoped user input is implemented. There is no private API,
credential scraping or automatic network provider in this module.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Protocol
import unicodedata

from app.osint.phone_intelligence import PhoneIntelligenceService
from app.osint.result import OsintFinding, ResultStatus


@dataclass(frozen=True, slots=True)
class PhoneTag:
    provider: str
    tag: str
    normalized_tag: str
    confidence: float
    retrieved_at: datetime
    source_type: str
    provenance: dict
    public_or_user_supplied: bool
    reliability: float

    def to_finding(self) -> OsintFinding:
        if not self.public_or_user_supplied:
            raise ValueError("Only public or explicitly user-supplied labels are supported.")
        if not self.tag.strip() or not self.provider.strip():
            raise ValueError("Phone tag and provider are required.")
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in (self.confidence, self.reliability)):
            raise ValueError("Tag confidence/reliability must be within 0..1.")
        return OsintFinding(
            category="community_label", value=self.tag, source=self.provider,
            confidence=min(self.confidence, 0.6), reliability=self.reliability,
            metadata={
                "normalized_tag": self.normalized_tag,
                "retrieved_at": self.retrieved_at.isoformat(),
                "source_type": self.source_type, "provenance": dict(self.provenance),
                "public_or_user_supplied": True, "lead_only": True,
                "quality": "unverified", "possible_alias": True,
                "owner_identity_confirmed": False,
            },
        )


@dataclass(slots=True)
class PhoneTagResult:
    provider: str
    status: ResultStatus
    tags: list[PhoneTag] = field(default_factory=list)
    error: str | None = None


class PhoneTagProvider(Protocol):
    def search(self, phone: str, *, case_id: str) -> PhoneTagResult: ...


class ManualPhoneTagProvider:
    """A caller supplies labels explicitly for one case and one E.164 number."""
    def __init__(self, *, case_id: str, phone: str, labels: list[str],
                 provenance: dict | None = None) -> None:
        result = PhoneIntelligenceService().analyze(phone)
        if not result.valid or not result.e164:
            raise ValueError("Manual phone labels require a valid E.164 number.")
        if not case_id:
            raise ValueError("Phone labels require a case scope.")
        self.case_id, self.phone = str(case_id), result.e164
        self.labels = tuple(labels[:50])
        self.provenance = dict(provenance or {})

    def search(self, phone: str, *, case_id: str) -> PhoneTagResult:
        if str(case_id) != self.case_id:
            return PhoneTagResult("manual", ResultStatus.NOT_SUPPORTED, error="Labels belong to another case.")
        parsed = PhoneIntelligenceService().analyze(phone)
        if parsed.e164 != self.phone:
            return PhoneTagResult("manual", ResultStatus.SUCCESS)
        tags, seen = [], set()
        for label in self.labels:
            tag = " ".join(unicodedata.normalize("NFC", str(label)).split())[:256]
            normalized = tag.casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tags.append(PhoneTag(
                provider="manual", tag=tag, normalized_tag=normalized,
                confidence=0.4, reliability=0.4, retrieved_at=datetime.now(timezone.utc),
                source_type="user_supplied", public_or_user_supplied=True,
                provenance={**self.provenance, "case_id": self.case_id,
                            "phone": self.phone, "network_used": False},
            ))
        return PhoneTagResult("manual", ResultStatus.SUCCESS, tags)


class DisabledCommunityPhoneTagProvider:
    def __init__(self, name: str = "getcontact") -> None:
        self.name = name

    def search(self, phone: str, *, case_id: str) -> PhoneTagResult:
        return PhoneTagResult(self.name, ResultStatus.NOT_AVAILABLE,
            error="No authorized official API configured; manual-assisted input only.")
