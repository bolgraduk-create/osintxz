"""Public social-content normalization and correlation foundation.

The contract is intentionally source-agnostic.  Collectors may emit public
posts/comments/replies later without forcing platform-specific structures into
analysis code.  Correlations are review signals only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
import re


_CONTENT_TYPES = {"post", "comment", "reply", "message", "bio", "repost", "share"}


@dataclass(frozen=True, slots=True)
class SocialContentItem:
    platform: str
    author: str
    content_type: str
    text: str
    url: str = ""
    timestamp: str = ""
    source: str = ""
    entities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "author": self.author,
            "contentType": self.content_type,
            "text": self.text,
            "url": self.url,
            "timestamp": self.timestamp,
            "source": self.source,
            "entities": list(self.entities),
        }


def normalize_social_content(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("contentType") or row.get("type") or "").strip().casefold()
        if kind not in _CONTENT_TYPES:
            continue
        text = _text(row)
        if not text:
            continue
        platform = str(row.get("platform") or row.get("service") or row.get("source") or "Unknown").strip()
        author = _author(row)
        url = str(row.get("url") or "").strip()
        timestamp = str(row.get("timestamp") or row.get("publishedAt") or row.get("createdAt") or "").strip()
        key = (platform.casefold(), author.casefold(), url.casefold(), text.casefold())
        if key in seen:
            continue
        seen.add(key)
        item = SocialContentItem(
            platform=platform,
            author=author,
            content_type=kind,
            text=text[:12000],
            url=url,
            timestamp=timestamp,
            source=str(row.get("source") or platform),
            entities=tuple(_entities(row, text)),
        )
        output.append(item.to_dict())
    return output


def correlate_social_content(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(item) for item in items if isinstance(item, dict)]
    correlations: list[dict[str, Any]] = []
    for left_index in range(len(rows)):
        left = rows[left_index]
        for right in rows[left_index + 1:]:
            if _same_author(left, right):
                continue
            shared = sorted(
                set(_tokens(left)) & set(_tokens(right))
            )
            if not shared:
                continue
            time_support = _time_proximity(left, right)
            score = min(100.0, len(shared) * 18.0 + time_support)
            if score < 36.0:
                continue
            correlations.append(
                {
                    "leftAuthor": str(left.get("author") or ""),
                    "rightAuthor": str(right.get("author") or ""),
                    "leftPlatform": str(left.get("platform") or ""),
                    "rightPlatform": str(right.get("platform") or ""),
                    "sharedSignals": shared[:8],
                    "timeProximityScore": round(time_support, 1),
                    "correlationScore": round(score, 1),
                    "correlationLabel": "Context overlap",
                    "correlationSummary": (
                        "Shared public-content context: "
                        + ", ".join(shared[:5])
                        + ". Treat as supporting evidence only."
                    ),
                    "leftUrl": str(left.get("url") or ""),
                    "rightUrl": str(right.get("url") or ""),
                }
            )
    correlations.sort(
        key=lambda item: (
            -float(item.get("correlationScore") or 0.0),
            str(item.get("leftAuthor") or ""),
            str(item.get("rightAuthor") or ""),
        )
    )
    return correlations[:200]


def _text(row: dict[str, Any]) -> str:
    for key in ("text", "body", "content", "detail", "description"):
        value = str(row.get(key) or "").strip()
        if value:
            return " ".join(value.split())
    return ""


def _author(row: dict[str, Any]) -> str:
    for key in ("author", "username", "handle", "account", "creator"):
        value = str(row.get(key) or "").strip().lstrip("@")
        if value:
            return value
    identifiers = row.get("identifiers")
    if isinstance(identifiers, dict):
        return str(identifiers.get("username") or identifiers.get("handle") or "").strip().lstrip("@")
    return ""


def _entities(row: dict[str, Any], text: str) -> list[str]:
    output: list[str] = []
    raw = row.get("entities")
    if isinstance(raw, list):
        output.extend(str(item).strip().casefold() for item in raw if str(item).strip())
    output.extend(match.casefold() for match in re.findall(r"(?<!\w)#[\w-]{3,64}", text, flags=re.UNICODE))
    output.extend(match.casefold() for match in re.findall(r"(?<!\w)@[A-Za-z0-9_.-]{3,64}", text))
    return list(dict.fromkeys(output))[:32]


def _tokens(item: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for entity in item.get("entities") or []:
        text = str(entity or "").strip().casefold()
        if text:
            tokens.append(text)
    words = re.findall(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ0-9_-]{5,}", str(item.get("text") or "").casefold())
    stop = {
        "about", "after", "before", "there", "their", "these", "those", "which",
        "будет", "котор", "этого", "после", "перед", "через", "очень", "просто",
    }
    tokens.extend(word for word in words if word not in stop)
    return list(dict.fromkeys(tokens))[:80]


def _same_author(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_author = str(left.get("author") or "").strip().casefold()
    right_author = str(right.get("author") or "").strip().casefold()
    left_platform = str(left.get("platform") or "").strip().casefold()
    right_platform = str(right.get("platform") or "").strip().casefold()
    return bool(left_author and left_author == right_author and left_platform == right_platform)


def _time_proximity(left: dict[str, Any], right: dict[str, Any]) -> float:
    a = _parse_time(left.get("timestamp"))
    b = _parse_time(right.get("timestamp"))
    if a is None or b is None:
        return 0.0
    days = abs((a - b).total_seconds()) / 86400.0
    if days <= 1:
        return 24.0
    if days <= 7:
        return 16.0
    if days <= 31:
        return 8.0
    return 0.0


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


__all__ = [
    "SocialContentItem",
    "normalize_social_content",
    "correlate_social_content",
]
