from __future__ import annotations

import json
from pathlib import Path

from app.application.public_social_activity import PublicSocialActivityCollector
from app.application.social_content_correlation import (
    build_social_intelligence,
    correlate_social_content,
    normalize_social_content,
)


class FakeResponse:
    def __init__(self, payload=None, *, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("GET", "https://example.test/")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "error",
                request=request,
                response=response,
            )

    def json(self):
        return self._payload


def test_bluesky_public_author_feed_normalizes_posts_and_replies():
    payload = {
        "feed": [
            {
                "post": {
                    "uri": "at://did:plc:test/app.bsky.feed.post/3abc",
                    "indexedAt": "2026-09-20T11:00:00Z",
                    "author": {"handle": "alpha.bsky.social"},
                    "record": {
                        "text": "Arrived in Kyiv #travel",
                        "createdAt": "2026-09-20T10:59:00Z",
                    },
                }
            },
            {
                "post": {
                    "uri": "at://did:plc:test/app.bsky.feed.post/3abd",
                    "author": {"handle": "alpha.bsky.social"},
                    "record": {
                        "text": "reply from Kyiv",
                        "createdAt": "2026-09-20T12:00:00Z",
                        "reply": {"root": {}, "parent": {}},
                    },
                }
            },
        ]
    }

    def transport(method, url, headers, timeout):
        assert method == "GET"
        assert url.startswith(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?"
        )
        assert "actor=alpha.bsky.social" in url
        assert timeout > 0
        return FakeResponse(payload)

    collector = PublicSocialActivityCollector(transport=transport)
    result = collector.collect(
        {
            "service": "Bluesky",
            "identifiers": {"username": "alpha.bsky.social"},
            "url": "https://bsky.app/profile/alpha.bsky.social",
        }
    )

    snapshot = result.to_dict()
    assert result.status == "success"
    assert snapshot["count"] == 2
    assert {item["contentType"] for item in snapshot["items"]} == {
        "post",
        "reply",
    }
    assert all(item["platform"] == "Bluesky" for item in snapshot["items"])
    assert snapshot["intelligence"]["summary"]["items"] == 2


def test_mastodon_uses_public_account_rss_without_login():
    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Public post</title>
          <link>https://mastodon.social/@alpha/114</link>
          <guid>https://mastodon.social/@alpha/114</guid>
          <pubDate>Sat, 20 Sep 2026 10:00:00 +0000</pubDate>
          <description><![CDATA[<p>Working in Odesa #osint</p>]]></description>
        </item>
      </channel>
    </rss>"""

    def transport(method, url, headers, timeout):
        assert method == "GET"
        assert url == "https://mastodon.social/@alpha.rss"
        assert "rss" in headers["Accept"]
        assert timeout > 0
        return FakeResponse(text=rss)

    result = PublicSocialActivityCollector(
        transport=transport
    ).collect(
        {
            "service": "Mastodon",
            "identifiers": {"username": "alpha"},
            "url": "https://mastodon.social/@alpha",
        }
    )

    snapshot = result.to_dict()
    assert result.status == "success"
    assert snapshot["count"] == 1
    assert snapshot["items"][0]["platform"] == "Mastodon"
    assert snapshot["items"][0]["text"] == "Working in Odesa #osint"


def test_mastodon_requires_instance_profile_url():
    capability = PublicSocialActivityCollector.capability(
        {
            "service": "Mastodon",
            "identifiers": {"username": "alpha"},
        }
    )
    assert capability["available"] is False
    assert "profile URL" in capability["reason"]


def test_social_intelligence_extracts_typed_context_and_builds_timeline():
    raw = [
        {
            "type": "post",
            "platform": "Bluesky",
            "author": "alpha",
            "text": "Meeting in Kyiv #osint https://example.org/project",
            "timestamp": "2026-09-20T10:00:00Z",
            "location": "Kyiv",
        },
        {
            "type": "comment",
            "platform": "GitHub",
            "author": "alpha_dev",
            "text": "Kyiv research #osint https://example.org/project",
            "timestamp": "2026-09-21T09:00:00Z",
            "city": "Kyiv",
        },
    ]

    normalized = normalize_social_content(raw)
    first_signals = set(normalized[0]["contextSignals"])
    assert "location:kyiv" in first_signals
    assert "hashtag:#osint" in first_signals
    assert "domain:example.org" in first_signals

    intelligence = build_social_intelligence(raw)
    assert intelligence["summary"] == {
        "items": 2,
        "authors": 2,
        "platforms": 2,
        "signals": len(intelligence["signals"]),
        "correlations": len(intelligence["correlations"]),
    }
    assert intelligence["summary"]["correlations"] >= 1
    assert intelligence["timeline"][0]["timestamp"] == "2026-09-21T09:00:00Z"

    correlations = correlate_social_content(normalized)
    assert correlations
    assert "location:kyiv" in correlations[0]["sharedContextSignals"]
    assert correlations[0]["timeProximityScore"] > 0
    assert correlations[0]["contextSupportScore"] > 0


def test_social_workspace_is_exposed_without_replacing_existing_tabs():
    qml = Path(
        "app/interface/desktop/qml/pages/Search.qml"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/investigation_search_bridge.py"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/unified_investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    collector = Path(
        "app/application/public_social_activity.py"
    ).read_text(encoding="utf-8")

    for token in (
        '{ key: "social", label: "Social" }',
        'activeTab === "social"',
        "runData.socialIntelligence",
        "row.contextSignals",
        '"Collect activity"',
        '"Accounts"',
        '"Mentions"',
        '"Correlation"',
    ):
        assert token in qml

    for token in (
        "build_social_intelligence",
        'self._run["socialIntelligence"]',
        'summary["socialAuthors"]',
        'summary["socialPlatforms"]',
        'summary["socialSignals"]',
    ):
        assert token in bridge

    for token in (
        "build_social_intelligence",
        '"socialIntelligence": social_intelligence',
    ):
        assert token in worker

    for token in (
        "public.api.bsky.app",
        "mastodon_account_rss",
        '"bluesky"',
        '"mastodon"',
    ):
        assert token in collector
