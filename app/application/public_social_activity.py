"""Bounded public social/activity collection for confirmed or reviewable accounts.

Supported without private credentials:
- GitHub public user events
- GitLab public user events
- Bluesky public author feed
- Mastodon account RSS feed

Collection is deliberately explicit/opt-in from the account details UI.  It
does not log in, bypass access controls, scrape private content, or infer that
two accounts belong to the same person.  Collected rows can be attached to the
selected PERSON as ordinary Evidence while preserving the public source URL.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable
from html.parser import HTMLParser
from urllib.parse import quote, urlencode, urlsplit
from xml.etree import ElementTree

import httpx

from app.application.social_content_correlation import (
    build_social_intelligence,
    correlate_social_content,
    normalize_social_content,
)
from app.models.evidence import EvidenceType
from app.models.source import SourceType


@dataclass(frozen=True, slots=True)
class PublicActivityResult:
    platform: str
    username: str
    items: tuple[dict[str, Any], ...]
    status: str = "success"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        normalized = normalize_social_content(self.items)
        intelligence = build_social_intelligence(normalized)
        return {
            "platform": self.platform,
            "username": self.username,
            "status": self.status,
            "error": self.error,
            "items": normalized,
            "correlations": correlate_social_content(normalized),
            "intelligence": intelligence,
            "count": len(normalized),
        }


Transport = Callable[..., httpx.Response]


class PublicSocialActivityCollector:
    """Small dispatcher for bounded public activity endpoints."""

    MAX_ITEMS = 100

    def __init__(self, *, transport: Transport | None = None) -> None:
        self.transport = transport

    @classmethod
    def capability(cls, account: dict[str, Any]) -> dict[str, Any]:
        username = cls._username(account)
        platform = cls._platform(account)
        supported = platform in {"github", "gitlab", "bluesky", "mastodon"} and bool(username)
        reason = ""
        if not username:
            reason = "Unable to determine account username."
        elif platform not in {"github", "gitlab", "bluesky", "mastodon"}:
            reason = "Public activity collection is currently supported for GitHub and GitLab, plus Bluesky and Mastodon."
        elif platform == "mastodon" and not cls._mastodon_profile_url(account):
            supported = False
            reason = "Mastodon collection requires a public profile URL on the account's instance."
        return {
            "available": supported,
            "platform": platform,
            "username": username,
            "reason": reason,
        }

    def collect(
        self,
        account: dict[str, Any],
        *,
        limit: int = 50,
        timeout: float = 12.0,
    ) -> PublicActivityResult:
        capability = self.capability(account)
        platform = str(capability["platform"])
        username = str(capability["username"])
        if not capability["available"]:
            return PublicActivityResult(
                platform=platform,
                username=username,
                items=(),
                status="not_supported",
                error=str(capability["reason"]),
            )
        bounded = max(1, min(int(limit), self.MAX_ITEMS))
        try:
            if platform == "github":
                items = self._github(username, limit=bounded, timeout=timeout)
            elif platform == "gitlab":
                items = self._gitlab(username, limit=bounded, timeout=timeout)
            elif platform == "bluesky":
                items = self._bluesky(username, limit=bounded, timeout=timeout)
            else:
                items = self._mastodon(
                    username,
                    profile_url=self._mastodon_profile_url(account),
                    limit=bounded,
                    timeout=timeout,
                )
            return PublicActivityResult(
                platform=platform,
                username=username,
                items=tuple(items[:bounded]),
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            return PublicActivityResult(
                platform=platform,
                username=username,
                items=(),
                status="failed",
                error=f"{platform.title()} returned HTTP {code}.",
            )
        except Exception as exc:
            return PublicActivityResult(
                platform=platform,
                username=username,
                items=(),
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )

    def _request_json(self, url: str, *, timeout: float) -> Any:
        headers = {
            "User-Agent": "OSINTXZ/1.0 PublicSocialActivity",
            "Accept": "application/json",
        }
        if self.transport is not None:
            response = self.transport("GET", url, headers=headers, timeout=timeout)
        else:
            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
        response.raise_for_status()
        return response.json()

    def _github(self, username: str, *, limit: int, timeout: float) -> list[dict[str, Any]]:
        per_page = min(limit, 100)
        payload = self._request_json(
            "https://api.github.com/users/"
            + quote(username, safe="")
            + f"/events/public?per_page={per_page}",
            timeout=timeout,
        )
        rows = payload if isinstance(payload, list) else []
        output: list[dict[str, Any]] = []
        for event in rows:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type") or "")
            repo = event.get("repo") if isinstance(event.get("repo"), dict) else {}
            payload_obj = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            repo_name = str(repo.get("name") or "")
            created = str(event.get("created_at") or "")
            event_id = str(event.get("id") or "")
            base_url = "https://github.com/" + repo_name if repo_name else "https://github.com/" + username

            if event_type == "IssueCommentEvent":
                comment = payload_obj.get("comment") if isinstance(payload_obj.get("comment"), dict) else {}
                text = str(comment.get("body") or "").strip()
                if text:
                    output.append(self._item(
                        platform="GitHub", author=username, content_type="comment",
                        text=text, url=str(comment.get("html_url") or base_url),
                        timestamp=created, source="github_public_events",
                        external_id=str(comment.get("id") or event_id),
                        context=repo_name,
                    ))
            elif event_type in {"IssuesEvent", "PullRequestEvent"}:
                key = "issue" if event_type == "IssuesEvent" else "pull_request"
                obj = payload_obj.get(key) if isinstance(payload_obj.get(key), dict) else {}
                text = " ".join(
                    part for part in (
                        str(obj.get("title") or "").strip(),
                        str(obj.get("body") or "").strip(),
                    ) if part
                )
                if text:
                    output.append(self._item(
                        platform="GitHub", author=username,
                        content_type="post", text=text,
                        url=str(obj.get("html_url") or base_url),
                        timestamp=created, source="github_public_events",
                        external_id=str(obj.get("id") or event_id),
                        context=repo_name,
                    ))
            elif event_type == "PushEvent":
                commits = payload_obj.get("commits") if isinstance(payload_obj.get("commits"), list) else []
                for commit in commits[:20]:
                    if not isinstance(commit, dict):
                        continue
                    text = str(commit.get("message") or "").strip()
                    if not text:
                        continue
                    sha = str(commit.get("sha") or "")
                    url = base_url + ("/commit/" + sha if sha else "")
                    output.append(self._item(
                        platform="GitHub", author=username,
                        content_type="post", text=text, url=url,
                        timestamp=created, source="github_public_events",
                        external_id=sha or event_id, context=repo_name,
                    ))
        return output

    def _gitlab(self, username: str, *, limit: int, timeout: float) -> list[dict[str, Any]]:
        users = self._request_json(
            "https://gitlab.com/api/v4/users?username="
            + quote(username, safe="")
            + "&per_page=20",
            timeout=timeout,
        )
        matches = users if isinstance(users, list) else []
        exact = next(
            (
                row for row in matches
                if isinstance(row, dict)
                and str(row.get("username") or "").casefold() == username.casefold()
            ),
            None,
        )
        if exact is None:
            return []
        user_id = str(exact.get("id") or "")
        if not user_id:
            return []
        events = self._request_json(
            "https://gitlab.com/api/v4/users/"
            + quote(user_id, safe="")
            + f"/events?per_page={min(limit, 100)}",
            timeout=timeout,
        )
        rows = events if isinstance(events, list) else []
        output: list[dict[str, Any]] = []
        for event in rows:
            if not isinstance(event, dict):
                continue
            note = event.get("note") if isinstance(event.get("note"), dict) else {}
            push = event.get("push_data") if isinstance(event.get("push_data"), dict) else {}
            text = str(
                note.get("body")
                or push.get("commit_title")
                or event.get("target_title")
                or ""
            ).strip()
            if not text:
                continue
            kind = "comment" if note else "post"
            project_id = str(event.get("project_id") or "")
            target_id = str(event.get("target_iid") or event.get("target_id") or "")
            url = str(event.get("target_url") or "")
            if not url and project_id:
                url = f"https://gitlab.com/projects/{project_id}"
            output.append(self._item(
                platform="GitLab", author=username, content_type=kind,
                text=text, url=url, timestamp=str(event.get("created_at") or ""),
                source="gitlab_public_events",
                external_id=str(event.get("id") or target_id),
                context=str(event.get("target_type") or ""),
            ))
        return output

    def _bluesky(self, username: str, *, limit: int, timeout: float) -> list[dict[str, Any]]:
        query = urlencode(
            {
                "actor": username,
                "limit": min(limit, 100),
                "filter": "posts_and_author_threads",
            }
        )
        payload = self._request_json(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + query,
            timeout=timeout,
        )
        feed = payload.get("feed") if isinstance(payload, dict) else []
        rows = feed if isinstance(feed, list) else []
        output: list[dict[str, Any]] = []
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            post = entry.get("post") if isinstance(entry.get("post"), dict) else {}
            record = post.get("record") if isinstance(post.get("record"), dict) else {}
            text = str(record.get("text") or "").strip()
            if not text:
                continue
            uri = str(post.get("uri") or "")
            rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
            author = post.get("author") if isinstance(post.get("author"), dict) else {}
            handle = str(author.get("handle") or username)
            url = (
                f"https://bsky.app/profile/{handle}/post/{rkey}"
                if rkey
                else f"https://bsky.app/profile/{handle}"
            )
            kind = "reply" if isinstance(record.get("reply"), dict) else "post"
            reason = entry.get("reason") if isinstance(entry.get("reason"), dict) else {}
            reason_type = str(reason.get("$type") or "").casefold()
            if "repost" in reason_type:
                kind = "repost"
            output.append(
                self._item(
                    platform="Bluesky",
                    author=handle,
                    content_type=kind,
                    text=text,
                    url=url,
                    timestamp=str(record.get("createdAt") or post.get("indexedAt") or ""),
                    source="bluesky_public_author_feed",
                    external_id=uri or rkey,
                    context="",
                )
            )
        return output

    def _mastodon(
        self,
        username: str,
        *,
        profile_url: str,
        limit: int,
        timeout: float,
    ) -> list[dict[str, Any]]:
        clean_profile = str(profile_url or "").rstrip("/")
        if not clean_profile:
            return []
        feed_url = clean_profile + ".rss"
        text = self._request_text(feed_url, timeout=timeout)
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return []

        output: list[dict[str, Any]] = []
        for item in root.findall(".//item")[:limit]:
            title = self._xml_text(item.find("title"))
            description = self._xml_text(item.find("description"))
            content = ""
            for child in list(item):
                if str(child.tag).endswith("encoded"):
                    content = self._xml_text(child)
                    break
            body = self._html_to_text(content or description or title)
            if not body:
                continue
            link = self._xml_text(item.find("link")) or clean_profile
            guid = self._xml_text(item.find("guid"))
            pub_date = self._xml_text(item.find("pubDate"))
            output.append(
                self._item(
                    platform="Mastodon",
                    author=username,
                    content_type="post",
                    text=body,
                    url=link,
                    timestamp=pub_date,
                    source="mastodon_account_rss",
                    external_id=guid or link,
                    context=str(urlsplit(clean_profile).hostname or ""),
                )
            )
        return output

    def _request_text(self, url: str, *, timeout: float) -> str:
        headers = {
            "User-Agent": "OSINTXZ/1.0 PublicSocialActivity",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        }
        if self.transport is not None:
            response = self.transport("GET", url, headers=headers, timeout=timeout)
        else:
            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
        response.raise_for_status()
        return str(response.text or "")

    @staticmethod
    def _xml_text(node: Any) -> str:
        if node is None:
            return ""
        return "".join(node.itertext()).strip()

    @staticmethod
    def _html_to_text(value: str) -> str:
        class _TextParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.parts: list[str] = []

            def handle_data(self, data: str) -> None:
                text = " ".join(str(data or "").split())
                if text:
                    self.parts.append(text)

        parser = _TextParser()
        try:
            parser.feed(str(value or ""))
            parser.close()
        except Exception:
            return " ".join(str(value or "").split())
        return " ".join(parser.parts)

    @staticmethod
    def _item(
        *,
        platform: str,
        author: str,
        content_type: str,
        text: str,
        url: str,
        timestamp: str,
        source: str,
        external_id: str,
        context: str,
    ) -> dict[str, Any]:
        return {
            "platform": platform,
            "author": author,
            "type": content_type,
            "text": text[:12000],
            "url": url,
            "timestamp": timestamp,
            "source": source,
            "externalId": external_id,
            "context": context,
        }

    @staticmethod
    def _username(account: dict[str, Any]) -> str:
        identifiers = account.get("identifiers")
        if isinstance(identifiers, dict):
            for key in (
                "username", "handle", "GITHUB_USERNAME", "GITLAB_USERNAME",
                "github_username", "gitlab_username", "BLUESKY_HANDLE",
                "bluesky_handle", "MASTODON_USERNAME", "mastodon_username",
            ):
                value = str(identifiers.get(key) or "").strip().lstrip("@")
                if value:
                    return value
        for key in ("username", "seed", "title"):
            value = str(account.get(key) or "").strip().lstrip("@")
            if value and " " not in value:
                return value
        return ""

    @staticmethod
    def _platform(account: dict[str, Any]) -> str:
        text = " ".join(
            str(account.get(key) or "")
            for key in ("service", "platform", "source", "url")
        ).casefold()
        if "github" in text:
            return "github"
        if "gitlab" in text:
            return "gitlab"
        if "bsky.app" in text or "bluesky" in text:
            return "bluesky"
        identifiers = account.get("identifiers")
        identifiers = identifiers if isinstance(identifiers, dict) else {}
        if (
            "mastodon" in text
            or "fediverse" in text
            or bool(
                identifiers.get("MASTODON_USERNAME")
                or identifiers.get("mastodon_username")
            )
        ):
            return "mastodon"
        return ""

    @staticmethod
    def _mastodon_profile_url(account: dict[str, Any]) -> str:
        for key in ("url", "profileUrl", "sourceUrl"):
            value = str(account.get(key) or "").strip()
            if not value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme in {"http", "https"} and parsed.hostname and "/@" in parsed.path:
                return value.rstrip("/")
        return ""


class PublicSocialActivityPersistenceService:
    """Persist public activity as deduplicated MESSAGE Evidence linked to PERSON."""

    WORKFLOW = "public_social_activity"

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

    def persist(
        self,
        *,
        person: Any,
        platform: str,
        username: str,
        items: list[dict[str, Any]],
    ) -> dict[str, int]:
        existing = self._existing_keys(getattr(person, "id", None))
        created = 0
        duplicates = 0
        if not items:
            return {"created": 0, "duplicates": 0}

        source = self.source_service.create_source(
            case_id=getattr(person, "case_id"),
            name=f"Public activity · {platform} · @{username}"[:255],
            source_type=SourceType.API,
            path=f"public-social://{platform.casefold()}/{username}",
            description="Public account activity collected explicitly by the analyst.",
        )
        for item in items:
            key = self._item_key(platform=platform, username=username, item=item)
            if key in existing:
                duplicates += 1
                continue
            metadata = {
                "workflow": self.WORKFLOW,
                "platform": platform,
                "username": username,
                "content_type": str(item.get("contentType") or item.get("type") or ""),
                "url": str(item.get("url") or ""),
                "timestamp": str(item.get("timestamp") or ""),
                "external_id": str(item.get("externalId") or ""),
                "item_key": key,
                "public_content": True,
                "ownership_inference_prohibited": True,
            }
            evidence = self.evidence_service.create_evidence(
                case_id=getattr(person, "case_id"),
                source_id=source.id,
                evidence_type=EvidenceType.MESSAGE,
                title=(
                    f"{platform} {metadata['content_type'] or 'activity'} · @{username}"
                )[:255],
                value=str(item.get("text") or "")[:1024] or None,
                description=str(item.get("text") or "")[:12000],
                metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            )
            self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=getattr(person, "id"),
            )
            existing.add(key)
            created += 1
        return {"created": created, "duplicates": duplicates}

    def _existing_keys(self, person_id: Any) -> set[str]:
        if person_id is None:
            return set()
        try:
            rows = list(
                self.evidence_link_service.get_evidence_objects_for_entity(person_id)
                or []
            )
        except Exception:
            return set()
        keys: set[str] = set()
        for row in rows:
            try:
                metadata = json.loads(str(getattr(row, "metadata_json", "") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if not isinstance(metadata, dict) or metadata.get("workflow") != self.WORKFLOW:
                continue
            key = str(metadata.get("item_key") or "")
            if key:
                keys.add(key)
        return keys

    @staticmethod
    def _item_key(*, platform: str, username: str, item: dict[str, Any]) -> str:
        raw = "\n".join(
            (
                platform.casefold(),
                username.casefold(),
                str(item.get("externalId") or ""),
                str(item.get("url") or ""),
                str(item.get("timestamp") or ""),
                str(item.get("text") or ""),
            )
        )
        return sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


__all__ = [
    "PublicActivityResult",
    "PublicSocialActivityCollector",
    "PublicSocialActivityPersistenceService",
]
