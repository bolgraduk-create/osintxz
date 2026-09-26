"""Source-agnostic public social-content normalization and correlation.

The module intentionally separates observations from identity conclusions.
Signals such as shared locations, organizations, hashtags, domains or timing
can support analyst review, but never auto-confirm account ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import urlsplit
import re


_CONTENT_TYPES = {"post", "comment", "reply", "message", "bio", "repost", "share"}
_EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.I)
_URL_RE = re.compile(r"https?://[^\s<>()\]\[\"']+", re.I)
_HASHTAG_RE = re.compile(r"(?<!\w)#[\w-]{3,64}", re.UNICODE)
_MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_.-]{3,64}")


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
    context_signals: tuple[str, ...] = ()

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
            "contextSignals": list(self.context_signals),
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
        entities = tuple(_entities(row, text))
        context = tuple(_context_signals(row, text, entities))
        item = SocialContentItem(
            platform=platform,
            author=author,
            content_type=kind,
            text=text[:12000],
            url=url,
            timestamp=timestamp,
            source=str(row.get("source") or platform),
            entities=entities,
            context_signals=context,
        )
        output.append(item.to_dict())
    output.sort(
        key=lambda item: (
            _time_sort_key(item.get("timestamp")),
            str(item.get("platform") or "").casefold(),
            str(item.get("author") or "").casefold(),
        ),
        reverse=True,
    )
    return output


def correlate_social_content(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(item) for item in items if isinstance(item, dict)]
    correlations: list[dict[str, Any]] = []
    for left_index in range(len(rows)):
        left = rows[left_index]
        for right in rows[left_index + 1:]:
            if _same_author(left, right):
                continue

            shared_context = sorted(set(_context_tokens(left)) & set(_context_tokens(right)))
            shared_terms = sorted(set(_tokens(left)) & set(_tokens(right)))
            shared = list(dict.fromkeys(shared_context + shared_terms))
            if not shared:
                continue

            time_support = _time_proximity(left, right)
            context_support = min(48.0, len(shared_context) * 16.0)
            lexical_support = min(24.0, len(shared_terms) * 6.0)
            score = min(100.0, context_support + lexical_support + time_support)
            if score < 36.0:
                continue

            correlations.append(
                {
                    "leftAuthor": str(left.get("author") or ""),
                    "rightAuthor": str(right.get("author") or ""),
                    "leftPlatform": str(left.get("platform") or ""),
                    "rightPlatform": str(right.get("platform") or ""),
                    "sharedSignals": shared[:10],
                    "sharedContextSignals": shared_context[:8],
                    "timeProximityScore": round(time_support, 1),
                    "contextSupportScore": round(context_support, 1),
                    "lexicalSupportScore": round(lexical_support, 1),
                    "correlationScore": round(score, 1),
                    "correlationLabel": "Context overlap",
                    "correlationSummary": (
                        "Shared public-content context: "
                        + ", ".join(shared[:5])
                        + ". Treat as supporting evidence only."
                    ),
                    "leftUrl": str(left.get("url") or ""),
                    "rightUrl": str(right.get("url") or ""),
                    "leftTimestamp": str(left.get("timestamp") or ""),
                    "rightTimestamp": str(right.get("timestamp") or ""),
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


def build_social_intelligence(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_social_content(items)
    correlations = correlate_social_content(normalized)

    platforms: dict[str, int] = {}
    authors: dict[str, dict[str, Any]] = {}
    signals: dict[str, int] = {}

    for item in normalized:
        platform = str(item.get("platform") or "Unknown")
        platforms[platform] = platforms.get(platform, 0) + 1

        author = str(item.get("author") or "Unknown")
        author_key = platform.casefold() + "::" + author.casefold()
        bucket = authors.setdefault(
            author_key,
            {
                "author": author,
                "platform": platform,
                "items": 0,
                "posts": 0,
                "comments": 0,
                "replies": 0,
                "firstSeen": "",
                "lastSeen": "",
            },
        )
        bucket["items"] += 1
        kind = str(item.get("contentType") or "")
        if kind == "post":
            bucket["posts"] += 1
        elif kind == "comment":
            bucket["comments"] += 1
        elif kind == "reply":
            bucket["replies"] += 1

        stamp = str(item.get("timestamp") or "")
        if stamp:
            if not bucket["firstSeen"] or stamp < bucket["firstSeen"]:
                bucket["firstSeen"] = stamp
            if not bucket["lastSeen"] or stamp > bucket["lastSeen"]:
                bucket["lastSeen"] = stamp

        for signal in item.get("contextSignals") or []:
            text = str(signal or "").strip()
            if text:
                signals[text] = signals.get(text, 0) + 1

    author_rows = sorted(
        authors.values(),
        key=lambda row: (-int(row["items"]), str(row["platform"]), str(row["author"])),
    )
    signal_rows = [
        {"signal": key, "count": value}
        for key, value in sorted(
            signals.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )
    ]

    return {
        "items": normalized,
        "correlations": correlations,
        "authors": author_rows,
        "platforms": [
            {"platform": platform, "count": count}
            for platform, count in sorted(
                platforms.items(),
                key=lambda pair: (-pair[1], pair[0]),
            )
        ],
        "signals": signal_rows[:100],
        "timeline": [
            {
                "timestamp": str(item.get("timestamp") or ""),
                "platform": str(item.get("platform") or ""),
                "author": str(item.get("author") or ""),
                "contentType": str(item.get("contentType") or ""),
                "text": str(item.get("text") or ""),
                "url": str(item.get("url") or ""),
                "contextSignals": list(item.get("contextSignals") or []),
            }
            for item in normalized
        ],
        "summary": {
            "items": len(normalized),
            "authors": len(author_rows),
            "platforms": len(platforms),
            "signals": len(signal_rows),
            "correlations": len(correlations),
        },
    }


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

    output.extend("hashtag:" + match.casefold() for match in _HASHTAG_RE.findall(text))
    output.extend("mention:" + match.casefold() for match in _MENTION_RE.findall(text))
    output.extend("email:" + match.casefold() for match in _EMAIL_RE.findall(text))

    for raw_url in _URL_RE.findall(text):
        clean = raw_url.rstrip(".,!?;:")
        output.append("url:" + clean.casefold())
        host = str(urlsplit(clean).hostname or "").casefold()
        if host:
            output.append("domain:" + host)

    return list(dict.fromkeys(output))[:48]


def _context_signals(
    row: dict[str, Any],
    text: str,
    entities: tuple[str, ...],
) -> list[str]:
    output: list[str] = list(entities)

    for key, prefix in (
        ("location", "location:"),
        ("city", "location:"),
        ("country", "location:"),
        ("place", "location:"),
        ("organization", "organization:"),
        ("company", "organization:"),
        ("context", "context:"),
    ):
        value = row.get(key)
        if isinstance(value, (str, int, float)):
            normalized = " ".join(str(value).strip().casefold().split())
            if normalized:
                output.append(prefix + normalized)

    tags = row.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            value = str(tag or "").strip().casefold()
            if value:
                output.append("tag:" + value)

    # Explicit geographic syntax such as "location: Kyiv" or "city=Odesa"
    for match in re.findall(
        r"\b(?:location|city|country|place)\s*[:=]\s*([A-Za-zА-Яа-яЁёІіЇїЄєҐґ][\w .'-]{2,48})",
        text,
        flags=re.I,
    ):
        normalized = " ".join(match.strip().casefold().split())
        if normalized:
            output.append("location:" + normalized)

    return list(dict.fromkeys(output))[:64]


def _context_tokens(item: dict[str, Any]) -> list[str]:
    values = item.get("contextSignals")
    if not isinstance(values, list):
        values = []
    return [
        str(value or "").strip().casefold()
        for value in values
        if str(value or "").strip()
    ]


def _tokens(item: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    words = re.findall(
        r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ0-9_-]{5,}",
        str(item.get("text") or "").casefold(),
    )
    stop = {
        "about", "after", "before", "there", "their", "these", "those", "which",
        "would", "could", "should", "https", "будет", "котор", "этого", "после",
        "перед", "через", "очень", "просто", "теперь", "этому", "когда",
    }
    tokens.extend(word for word in words if word not in stop)
    return list(dict.fromkeys(tokens))[:80]


def _same_author(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_author = str(left.get("author") or "").strip().casefold()
    right_author = str(right.get("author") or "").strip().casefold()
    left_platform = str(left.get("platform") or "").strip().casefold()
    right_platform = str(right.get("platform") or "").strip().casefold()
    return bool(
        left_author
        and left_author == right_author
        and left_platform == right_platform
    )


def _time_proximity(left: dict[str, Any], right: dict[str, Any]) -> float:
    a = _parse_time(left.get("timestamp"))
    b = _parse_time(right.get("timestamp"))
    if a is None or b is None:
        return 0.0
    days = abs((a - b).total_seconds()) / 86400.0
    if days <= 1:
        return 28.0
    if days <= 3:
        return 22.0
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


def _time_sort_key(value: Any) -> float:
    parsed = _parse_time(value)
    if parsed is None:
        return 0.0
    try:
        return parsed.timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


__all__ = [
    "SocialContentItem",
    "normalize_social_content",
    "correlate_social_content",
    "build_social_intelligence",
]
