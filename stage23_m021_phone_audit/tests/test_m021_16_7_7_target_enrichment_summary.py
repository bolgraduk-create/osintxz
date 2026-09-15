from types import SimpleNamespace

from app.application.investigation_target_enrichment_service import (
    InvestigationTargetEnrichmentSummary,
)
from app.osint.models import OsintTargetType


def test_summary_aggregates_persistence_counts():
    summary = InvestigationTargetEnrichmentSummary(
        target_type=OsintTargetType.PHONE,
        target_value="+380671234567",
        persistences=(
            SimpleNamespace(
                persisted_findings=3,
                sources_created=2,
                evidences_created=3,
                entities_created=2,
                links_created=3,
            ),
            SimpleNamespace(
                persisted_findings=4,
                sources_created=1,
                evidences_created=4,
                entities_created=1,
                links_created=4,
            ),
        ),
    )

    assert summary.persisted_findings == 7
    assert summary.sources_created == 3
    assert summary.evidences_created == 7
    assert summary.entities_created == 3
    assert summary.links_created == 7


def test_summary_provider_rows():
    record = SimpleNamespace(
        runtime_connector_name="LocalPhone",
        capability=SimpleNamespace(
            display_name="LocalPhone",
            module="local_phone",
        ),
        result=SimpleNamespace(
            connector="LocalPhone",
            status=SimpleNamespace(value="success"),
            findings=[1, 2],
            error=None,
        ),
    )
    execution = SimpleNamespace(
        route=SimpleNamespace(
            goal=SimpleNamespace(value="phone_enrichment")
        ),
        records=[record],
    )
    summary = InvestigationTargetEnrichmentSummary(
        target_type=OsintTargetType.PHONE,
        target_value="+380671234567",
        executions=(execution,),
    )

    rows = summary.provider_rows
    assert len(rows) == 1
    assert rows[0]["provider"] == "LocalPhone"
    assert rows[0]["goal"] == "phone_enrichment"
    assert rows[0]["status"] == "success"
    assert rows[0]["findings"] == 2
