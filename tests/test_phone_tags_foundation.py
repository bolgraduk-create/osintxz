from app.osint.capabilities import DiscoveryGoal
from app.osint.finding_persistence import OsintFindingPersistenceService
from app.osint.models import OsintTargetType
from app.osint.phone_tags import DisabledCommunityPhoneTagProvider, ManualPhoneTagProvider
from app.osint.result import ResultStatus
from tests.test_registry_persistence_integration import runtime


def test_manual_labels_are_case_scoped_deduplicated_unverified():
    provider = ManualPhoneTagProvider(case_id="case-a", phone="+380632874404", labels=["Example Label", " example label "])
    result = provider.search("+380 63 287 4404", case_id="case-a")
    assert len(result.tags) == 1
    finding = result.tags[0].to_finding()
    assert finding.category == "community_label"
    assert finding.metadata["owner_identity_confirmed"] is False
    assert finding.metadata["provenance"]["network_used"] is False
    assert OsintFindingPersistenceService._entity_candidates(finding) == ()
    assert provider.search("+380632874404", case_id="case-b").status is ResultStatus.NOT_SUPPORTED


def test_unconfigured_community_provider_never_accesses_private_api():
    result = DisabledCommunityPhoneTagProvider().search("+380632874404", case_id="case-a")
    assert result.status is ResultStatus.NOT_AVAILABLE and not result.tags


def test_manual_label_persists_only_evidence_with_provenance(runtime):
    _, case_id, services = runtime
    provider = ManualPhoneTagProvider(case_id=str(case_id), phone="+380632874404", labels=["Possible alias"])
    persistence = OsintFindingPersistenceService(
        source_service=services.source_service, evidence_service=services.evidence_service,
        entity_service=services.entity_service, evidence_link_service=services.evidence_link_service,
    )
    result = persistence.persist_findings(
        case_id=case_id, target_type=OsintTargetType.PHONE, target_value="+380632874404",
        goal=DiscoveryGoal.PHONE_ENRICHMENT, connector="manual_phone_tags",
        capability_module="manual_phone_tags", findings=[tag.to_finding() for tag in provider.search("+380632874404", case_id=str(case_id)).tags],
    )
    assert result.evidences_created == 1 and result.entities_created == 0
