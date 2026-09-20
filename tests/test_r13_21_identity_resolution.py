from pathlib import Path
from types import SimpleNamespace

from app.application.identity_resolution import (
    IdentitySignals,
    build_known_identity_profile,
    extract_identity_signals,
    resolve_identity,
    resolve_identity_record,
)
from app.application.investigation_result_consolidation import consolidate_result_rows


def _profile(**extra):
    data = {
        "firstName": "Марк",
        "lastName": "Кириченко",
        "birthDate": "2009-03-01",
        "city": "Bolhrad",
        "emails": "mark@example.com",
        "organizations": "Gymnasium",
    }
    data.update(extra)
    return build_known_identity_profile(data)


def test_name_only_is_insufficient_and_cannot_auto_pivot():
    profile = _profile(birthDate="", city="", emails="", organizations="")
    result = resolve_identity(profile, IdentitySignals(names={"Mark Kyrychenko"}))
    assert result.status == "insufficient"
    assert result.pivot_allowed is False
    assert result.score > 0


def test_full_name_plus_birth_date_is_supported_and_pivotable():
    result = resolve_identity(
        _profile(city="", emails="", organizations=""),
        IdentitySignals(names={"Mark Kyrychenko"}, birth_dates={"2009-03-01"}),
    )
    assert result.status in {"supported", "strong"}
    assert result.pivot_allowed is True
    assert "name" in result.matched_categories
    assert "birth_date" in result.matched_categories


def test_birth_date_conflict_blocks_identity_pivot():
    result = resolve_identity(
        _profile(city="", emails="", organizations=""),
        IdentitySignals(names={"Mark Kyrychenko"}, birth_dates={"2000-03-01"}),
    )
    assert result.status == "conflicting"
    assert result.pivot_allowed is False
    assert "birth_date" in result.conflict_categories


def test_name_plus_exact_email_is_strong_alignment():
    result = resolve_identity(
        _profile(birthDate="", city="", organizations=""),
        IdentitySignals(names={"Mark Kirichenko"}, emails={"mark@example.com"}),
    )
    assert result.status == "strong"
    assert result.pivot_allowed is True
    assert result.score >= 60


def test_location_and_organization_support_but_do_not_prove_identity_alone():
    result = resolve_identity(
        _profile(birthDate="", emails=""),
        IdentitySignals(
            names={"Mark Kyrychenko"},
            cities={"bolhrad"},
            organizations={"gymnasium"},
        ),
    )
    assert result.status == "supported"
    assert result.pivot_allowed is True
    assert set(result.matched_categories) >= {"name", "city", "organization"}


def test_record_extraction_uses_structured_signals_and_ignores_secret_fields():
    record = SimpleNamespace(
        display_name="Mark Kyrychenko",
        record_type="person",
        identifiers={"ORCID": "0000-0002-1825-0097"},
        attributes={
            "birth_date": "2009-03-01",
            "email": "mark@example.com",
            "city": "Bolhrad",
            "password": "do-not-use",
            "profile": {"organization": "Gymnasium"},
        },
        metadata={},
    )
    resolution, signals = resolve_identity_record(_profile(), record, person_query="Марк Кириченко")
    assert "2009-03-01" in signals.birth_dates
    assert "mark@example.com" in signals.emails
    assert "bolhrad" in signals.cities
    assert "gymnasium" in signals.organizations
    assert all("do-not-use" not in value for values in signals.to_payload().values() for value in values)
    assert resolution.status == "strong"


def test_conflicting_identity_is_removed_from_clean_but_kept_in_identity_view():
    profile = _profile(city="", emails="", organizations="")
    rows = [
        {
            "lane": "Federation",
            "source": "good",
            "title": "Mark Kyrychenko",
            "type": "person",
            "seed": "Марк Кириченко",
            "seedType": "person_name",
            "candidateOnly": True,
            "_identitySignals": IdentitySignals(
                names={"Mark Kyrychenko"}, birth_dates={"2009-03-01"}
            ).to_payload(),
        },
        {
            "lane": "Federation",
            "source": "wrong",
            "title": "Mark Kyrychenko",
            "detail": "different person",
            "type": "person",
            "seed": "Марк Кириченко",
            "seedType": "person_name",
            "candidateOnly": True,
            "_identitySignals": IdentitySignals(
                names={"Mark Kyrychenko"}, birth_dates={"1990-01-01"}
            ).to_payload(),
        },
    ]
    result = consolidate_result_rows(rows, identity_profile=profile)
    assert [row["source"] for row in result.rows] == ["good"]
    statuses = {row["source"]: row["identityStatus"] for row in result.identity_rows}
    assert statuses["good"] in {"supported", "strong"}
    assert statuses["wrong"] == "conflicting"
    assert result.identity_conflicting == 1


def test_identity_alignment_changes_result_ranking():
    profile = _profile(city="", organizations="")
    rows = [
        {
            "lane": "Federation", "source": "weak", "title": "Mark Kyrychenko",
            "detail": "candidate", "type": "person", "seed": "Марк Кириченко",
            "seedType": "person_name", "candidateOnly": True,
            "_identitySignals": IdentitySignals(names={"Mark Kyrychenko"}).to_payload(),
        },
        {
            "lane": "Federation", "source": "strong", "title": "Mark Kyrychenko",
            "detail": "structured profile", "type": "person", "seed": "Марк Кириченко",
            "seedType": "person_name", "candidateOnly": True,
            "_identitySignals": IdentitySignals(
                names={"Mark Kyrychenko"}, birth_dates={"2009-03-01"}, emails={"mark@example.com"}
            ).to_payload(),
        },
    ]
    result = consolidate_result_rows(rows, identity_profile=profile)
    assert result.rows[0]["source"] == "strong"
    assert result.rows[0]["identityStatus"] == "strong"


def test_worker_gates_person_name_pivots_on_multi_signal_resolution():
    source = Path("app/interface/desktop/workers/unified_investigation_search_worker.py").read_text(encoding="utf-8")
    assert "build_known_identity_profile(self.profile)" in source
    assert "resolution.pivot_allowed" in source
    assert "identity-supported pivot(s)" in source
    assert '"identityCandidates": identity_rows' in source


def test_qml_exposes_identity_view_and_explains_non_proof_semantics():
    qml = Path("app/interface/desktop/qml/pages/Search.qml").read_text(encoding="utf-8")
    assert '{ key: "identity", label: "Identity" }' in qml
    assert 'title: "Identity Leads"' in qml
    assert "identityAlignmentScore" in qml
    assert "Identity alignment is an explainable relevance score, not proof" in qml
