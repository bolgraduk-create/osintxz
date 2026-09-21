from __future__ import annotations

from pathlib import Path

from app.application.unified_target_profile import (
    build_unified_target_profile,
)


def _snapshot() -> dict:
    return {
        "id": "person-1",
        "title": "Alice Example",
        "normalizedValue": "alice example",
        "confidenceText": "95%",
        "caseTitle": "Demo",
        "avatarUrl": "",
        "relatedEntities": [
            {
                "id": "u1",
                "rawType": "username",
                "type": "Username",
                "value": "alice",
                "url": "https://github.com/alice",
                "confidence": "92%",
                "evidenceTitle": "GitHub profile",
                "basis": "evidence",
            },
            {
                "id": "e1",
                "rawType": "email",
                "type": "Email",
                "value": "alice@example.org",
                "confidence": "90%",
                "evidenceTitle": "Public record",
                "basis": "analyst_selected",
            },
            {
                "id": "o1",
                "rawType": "organization",
                "type": "Organization",
                "value": "Example Labs",
                "confidence": "88%",
                "evidenceTitle": "Company record",
                "basis": "evidence",
            },
            {
                "id": "l1",
                "rawType": "location",
                "type": "Location",
                "value": "Odesa",
                "confidence": "80%",
                "evidenceTitle": "Public profile",
                "basis": "manual",
            },
            {
                "id": "d1",
                "rawType": "domain",
                "type": "Domain",
                "value": "example.org",
                "confidence": "90%",
                "basis": "evidence",
            },
        ],
        "links": [
            {
                "label": "GitHub",
                "value": "alice",
                "url": "https://github.com/alice",
                "source": "GitHub",
                "evidenceTitle": "GitHub profile",
            },
            {
                "label": "Personal page",
                "value": "https://example.org/about",
                "url": "https://example.org/about",
                "source": "Public web",
            },
            {
                "label": "Unsafe",
                "value": "javascript:alert(1)",
                "url": "javascript:alert(1)",
            },
        ],
        "photos": [
            {
                "id": "photo-1",
                "title": "Portrait",
                "type": "Image",
                "mimeType": "image/jpeg",
                "date": "2026-09-01",
            }
        ],
        "files": [
            {
                "id": "file-1",
                "title": "CV.pdf",
                "type": "Document",
                "mimeType": "application/pdf",
                "date": "2026-09-02",
            }
        ],
        "evidence": [
            {"id": "ev1"},
            {"id": "ev2"},
            {"id": "ev3"},
        ],
        "mentions": [
            {"id": "m1"},
        ],
    }


def _group(profile: dict, key: str) -> list[dict]:
    return profile["groupMap"][key]


def test_unified_profile_groups_person_intelligence_without_new_claims():
    profile = build_unified_target_profile(_snapshot())

    assert profile["version"] == "R13.27a"
    assert profile["primary"]["name"] == "Alice Example"
    assert profile["counts"]["accounts"] == 1
    assert profile["counts"]["contacts"] == 1
    assert profile["counts"]["organizations"] == 1
    assert profile["counts"]["locations"] == 1
    assert profile["counts"]["documents"] == 2
    assert profile["counts"]["evidence"] == 3
    assert profile["counts"]["mentions"] == 1
    assert "not automatically" in profile["notice"]


def test_same_profile_url_is_not_counted_again_as_web_page():
    profile = build_unified_target_profile(_snapshot())

    accounts = _group(profile, "accounts")
    web = _group(profile, "webTechnical")

    assert any(row["url"] == "https://github.com/alice" for row in accounts)
    assert all(row["url"] != "https://github.com/alice" for row in web)
    assert any(row["url"] == "https://example.org/about" for row in web)


def test_unified_profile_rejects_non_http_external_urls():
    profile = build_unified_target_profile(_snapshot())
    values = [
        row.get("url")
        for group in profile["groups"]
        for row in group["rows"]
    ]

    assert "javascript:alert(1)" not in values


def test_unified_profile_preserves_association_provenance():
    profile = build_unified_target_profile(_snapshot())

    contact = _group(profile, "contacts")[0]
    location = _group(profile, "locations")[0]

    assert contact["basis"] == "analyst_selected"
    assert contact["basisLabel"] == "Analyst selected"
    assert location["basis"] == "manual"
    assert location["basisLabel"] == "Manual"

    provenance = {
        row["basis"]: row["count"]
        for row in profile["provenance"]
    }
    assert provenance["person_entity"] >= 1
    assert provenance["evidence"] >= 1
    assert provenance["analyst_selected"] == 1
    assert provenance["manual"] == 1
    assert provenance["managed_attachment"] == 2


def test_profile_coverage_means_populated_categories_not_identity_confidence():
    profile = build_unified_target_profile(
        {
            "id": "person-2",
            "title": "Only Name",
            "normalizedValue": "only name",
            "relatedEntities": [],
            "links": [],
            "photos": [],
            "files": [],
            "evidence": [],
            "mentions": [],
        }
    )

    assert profile["coverage"]["populatedGroups"] == 1
    assert profile["coverage"]["totalGroups"] == 7
    assert profile["coverage"]["percent"] == 14
    assert "profile categories populated" in profile["coverage"]["label"]
    assert profile["primary"]["confidenceText"] == ""


def test_unified_profile_metrics_have_stable_person_card_contract():
    profile = build_unified_target_profile(_snapshot())
    labels = [row["label"] for row in profile["metrics"]]

    assert labels == [
        "Accounts",
        "Contacts",
        "Organizations",
        "Locations",
        "Web / Tech",
        "Evidence",
        "Coverage",
    ]
    assert len(profile["groups"]) == 7


def test_desktop_bridge_attaches_projection_to_existing_person_snapshot():
    source = Path(
        "app/interface/desktop/bridges/desktop_bridge.py"
    ).read_text(encoding="utf-8")

    assert "build_unified_target_profile" in source
    assert 'snapshot["unifiedProfile"] = build_unified_target_profile(snapshot)' in source
    assert '"relatedEntities": related_rows[:100]' in source
    assert '"evidence": evidence_rows[:50]' in source


def test_person_qml_uses_backend_unified_profile_metrics_and_provenance():
    qml = Path(
        "app/interface/desktop/qml/pages/Person.qml"
    ).read_text(encoding="utf-8")

    assert "R13.27a UNIFIED TARGET PROFILE" in qml
    assert "root.person.unifiedProfile" in qml
    assert 'title: "Unified Target Profile"' in qml
    assert "root.unifiedProfile.metrics" in qml
    assert "unifiedProvenanceText" in qml
    assert "profileCoverage" in qml


def test_unified_profile_module_is_projection_only():
    source = Path(
        "app/application/unified_target_profile.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "session.commit",
        "container.commit",
        "create_evidence",
        "resolve_or_create_entity",
        "create_relationship",
    ):
        assert forbidden not in source
