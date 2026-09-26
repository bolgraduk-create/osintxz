from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
import json

from app.application.public_social_activity import (
    PublicSocialActivityCollector,
    PublicSocialActivityPersistenceService,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
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


def test_github_public_activity_collects_comments_posts_and_commit_messages():
    events = [
        {
            "id": "1",
            "type": "IssueCommentEvent",
            "created_at": "2026-09-01T10:00:00Z",
            "repo": {"name": "org/repo"},
            "payload": {
                "comment": {
                    "id": 10,
                    "body": "Working from Bangkok #travel",
                    "html_url": "https://github.com/org/repo/issues/1#issuecomment-10",
                }
            },
        },
        {
            "id": "2",
            "type": "PushEvent",
            "created_at": "2026-09-02T10:00:00Z",
            "repo": {"name": "org/repo"},
            "payload": {
                "commits": [
                    {
                        "sha": "abc",
                        "message": "fix Bangkok timezone handling",
                    }
                ]
            },
        },
    ]

    def transport(method, url, headers, timeout):
        assert method == "GET"
        assert "/users/alpha/events/public" in url
        assert headers["User-Agent"].startswith("OSINTXZ/")
        assert timeout > 0
        return FakeResponse(events)

    collector = PublicSocialActivityCollector(transport=transport)
    result = collector.collect(
        {
            "service": "GitHub",
            "identifiers": {"username": "alpha"},
            "url": "https://github.com/alpha",
        }
    )

    payload = result.to_dict()
    assert result.status == "success"
    assert payload["count"] == 2
    assert {item["contentType"] for item in payload["items"]} == {
        "comment",
        "post",
    }


def test_gitlab_public_activity_resolves_exact_user_before_events():
    calls = []

    def transport(method, url, headers, timeout):
        del method, headers, timeout
        calls.append(url)
        if "/users?username=" in url:
            return FakeResponse(
                [
                    {"id": 99, "username": "alpha"},
                    {"id": 100, "username": "alpha-other"},
                ]
            )
        return FakeResponse(
            [
                {
                    "id": 7,
                    "created_at": "2026-09-03T12:00:00Z",
                    "project_id": 42,
                    "target_type": "Issue",
                    "target_title": "Thailand research",
                    "note": {"body": "Bangkok notes"},
                }
            ]
        )

    result = PublicSocialActivityCollector(
        transport=transport
    ).collect(
        {
            "service": "GitLab",
            "identifiers": {"username": "alpha"},
        }
    )

    assert result.status == "success"
    assert len(result.items) == 1
    assert result.items[0]["type"] == "comment"
    assert any("/users/99/events" in url for url in calls)


def test_unsupported_platform_is_explicit_and_does_not_guess():
    result = PublicSocialActivityCollector().collect(
        {
            "service": "Instagram",
            "identifiers": {"username": "alpha"},
        }
    )

    assert result.status == "not_supported"
    assert result.items == ()
    assert "GitHub and GitLab" in result.error


class FakeSourceService:
    def __init__(self):
        self.rows = []

    def create_source(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row


class FakeEvidenceService:
    def __init__(self):
        self.rows = []

    def create_evidence(self, **kwargs):
        row = SimpleNamespace(id=uuid4(), **kwargs)
        self.rows.append(row)
        return row


class FakeLinkService:
    def __init__(self, evidence_service):
        self.evidence_service = evidence_service
        self.links = []

    def ensure_link(self, *, evidence_id, entity_id):
        self.links.append((evidence_id, entity_id))
        return SimpleNamespace(
            evidence_id=evidence_id,
            entity_id=entity_id,
        ), True

    def get_evidence_objects_for_entity(self, entity_id):
        ids = {
            evidence_id
            for evidence_id, linked_id in self.links
            if linked_id == entity_id
        }
        return [
            row
            for row in self.evidence_service.rows
            if row.id in ids
        ]


def test_public_activity_persistence_is_person_linked_and_idempotent():
    source = FakeSourceService()
    evidence = FakeEvidenceService()
    links = FakeLinkService(evidence)
    service = PublicSocialActivityPersistenceService(
        source_service=source,
        evidence_service=evidence,
        evidence_link_service=links,
    )
    person = SimpleNamespace(
        id=uuid4(),
        case_id=uuid4(),
    )
    items = [
        {
            "platform": "GitHub",
            "author": "alpha",
            "contentType": "comment",
            "text": "Public comment",
            "url": "https://github.com/x/y#1",
            "timestamp": "2026-09-01T00:00:00Z",
        }
    ]

    first = service.persist(
        person=person,
        platform="GitHub",
        username="alpha",
        items=items,
    )
    second = service.persist(
        person=person,
        platform="GitHub",
        username="alpha",
        items=items,
    )

    assert first == {"created": 1, "duplicates": 0}
    assert second == {"created": 0, "duplicates": 1}
    assert len(evidence.rows) == 1
    metadata = json.loads(evidence.rows[0].metadata_json)
    assert metadata["workflow"] == "public_social_activity"
    assert metadata["public_content"] is True
    assert metadata["ownership_inference_prohibited"] is True
    assert (evidence.rows[0].id, person.id) in links.links


def test_search_ui_exposes_opt_in_activity_collection_without_replacing_existing_flow():
    from pathlib import Path

    qml = Path(
        "app/interface/desktop/qml/pages/Search.qml"
    ).read_text(encoding="utf-8")
    bridge = Path(
        "app/interface/desktop/bridges/investigation_search_bridge.py"
    ).read_text(encoding="utf-8")
    worker = Path(
        "app/interface/desktop/workers/public_social_activity_worker.py"
    ).read_text(encoding="utf-8")

    for token in (
        'text: root.socialActivityBusy',
        '"Collect activity"',
        "investigationSearchBridge.collectPublicActivity",
        "investigationSearchBridge.socialActivityCapability",
        "root.socialActivity.items",
        "PUBLIC ACTIVITY",
    ):
        assert token in qml

    for token in (
        "def collectPublicActivity(",
        "def socialActivityCapability(",
        "PublicSocialActivityWorker",
        "correlate_social_content",
        'self._run["socialContent"]',
        'self._run["socialCorrelations"]',
    ):
        assert token in bridge

    assert "PublicSocialActivityPersistenceService" in worker

    # Existing account enrichment and search paths remain in place.
    assert "deepEnrichAccount" in qml
    assert "accountEnrichmentCapability" in qml
    assert "UnifiedInvestigationSearchWorker" in bridge
