from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
    RecursiveEnrichmentSeed,
    RecursiveExpansionStopReason,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotPolicyLimits, PivotTraversalState


class FakeRun:
    def __init__(self, *, depth: int, value: str):
        self.depth = depth
        self.value = value
        self.persisted_findings = 1
        self.entities_created = 1
        self.sources_created = 1
        self.evidences_created = 1


class FakeEnrichmentService:
    def __init__(self):
        self.calls = []
        limits = PivotPolicyLimits(
            max_depth=3,
            max_pivots_per_entity=8,
            max_new_entities=50,
        )
        self.execution_service = SimpleNamespace(
            router=SimpleNamespace(
                policy=SimpleNamespace(
                    limits=limits,
                )
            )
        )

    def enrich_target(self, **kwargs):
        self.calls.append(kwargs)
        return FakeRun(
            depth=kwargs["depth"],
            value=kwargs["value"],
        )


class ChainCandidatePolicy:
    def from_enrichment_result(self, run, *, next_depth):
        # Produce one new unique target after every run.
        entity_id = uuid4()
        return (
            SimpleNamespace(
                target_type=OsintTargetType.URL,
                value=f"https://example.com/{next_depth}/{entity_id.hex[:6]}",
                entity_id=entity_id,
                depth=next_depth,
            ),
        )


def test_recursive_progress_reports_each_target_and_max_target_stop():
    enrichment = FakeEnrichmentService()
    progress = []

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=ChainCandidatePolicy(),
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
        state=PivotTraversalState(),
        timeout=5,
        progress_callback=progress.append,
        max_targets=2,
        time_budget_seconds=30,
    )

    assert result.targets_processed == 2
    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.MAX_TARGETS_REACHED
    )

    phases = [item.phase for item in progress]

    assert phases[0] == "queue_seeded"
    assert phases.count("target_started") == 2
    assert phases.count("target_finished") == 2
    assert phases[-1] == "stopped"

    started = [
        item for item in progress
        if item.phase == "target_started"
    ]
    assert started[0].depth == 0
    assert started[0].value == "example.com"
    assert started[1].depth == 1


def test_recursive_progress_callback_failure_does_not_break_collection():
    enrichment = FakeEnrichmentService()

    def broken_callback(_progress):
        raise RuntimeError("UI callback failure")

    service = OsintRecursiveEnrichmentService(
        enrichment_service=enrichment,
        candidate_policy=ChainCandidatePolicy(),
    )

    result = service.enrich(
        case_id=uuid4(),
        seeds=(
            RecursiveEnrichmentSeed(
                target_type=OsintTargetType.DOMAIN,
                value="example.com",
            ),
        ),
        max_targets=1,
        progress_callback=broken_callback,
    )

    assert result.targets_processed == 1
    assert (
        result.stop_reason
        is RecursiveExpansionStopReason.MAX_TARGETS_REACHED
    )
