from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.interface.desktop.workers.investigation_search_worker import (
    InvestigationSearchWorker,
)


class FakeRecursive:
    def __init__(self):
        self.calls = []

    def enrich(self, **kwargs):
        self.calls.append(kwargs)
        callback = kwargs["progress_callback"]
        callback(
            SimpleNamespace(
                phase="target_started",
                target_type=SimpleNamespace(value="domain"),
                value="example.com",
                depth=0,
                targets_processed=0,
                queued_targets=0,
                candidates_discovered=0,
                candidates_enqueued=0,
                new_entities_count=0,
                persisted_findings=0,
                entities_created=0,
                elapsed_seconds=1.2,
                stop_reason=None,
            )
        )
        return SimpleNamespace(
            runs=[
                SimpleNamespace(
                    executions=[],
                    persistence=[],
                    depth=0,
                )
            ],
            state=SimpleNamespace(),
        )


class FakeOpenWeb:
    def enrich(self, *args, **kwargs):
        return SimpleNamespace(
            query=SimpleNamespace(depth=0),
            persistence=[],
        )


class FakeOpenWebRecursive:
    def __init__(self):
        self.calls = []

    def expand(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            recursion=None,
            candidates_discovered=0,
            recursive_targets_processed=0,
        )


def test_worker_uses_bounded_interactive_recursive_search_and_emits_progress():
    recursive = FakeRecursive()
    bridge = FakeOpenWebRecursive()

    container = SimpleNamespace(
        osint_recursive_enrichment_service=recursive,
        osint_enrichment_service=SimpleNamespace(),
        open_web_enrichment_service=FakeOpenWeb(),
        open_web_recursive_pivot_service=bridge,
    )

    worker = InvestigationSearchWorker(
        container=container,
        case_id=uuid4(),
        raw_target="example.com",
        recursive=True,
    )

    statuses = []
    failures = []
    worker.status_changed.connect(statuses.append)
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert recursive.calls

    call = recursive.calls[0]
    assert call["timeout"] == 15
    assert call["max_targets"] == 6
    assert call["time_budget_seconds"] == 150.0
    assert call["per_target_new_entity_limit"] == 5
    assert callable(call["progress_callback"])

    assert any(
        "depth=0" in status
        and "example.com" in status
        and "Ожидание источников" in status
        for status in statuses
    )

    assert bridge.calls
    bridge_call = bridge.calls[0]
    assert bridge_call["timeout"] == 15
    assert bridge_call["max_targets"] == 4
    assert bridge_call["time_budget_seconds"] == 90.0
    assert bridge_call["per_target_new_entity_limit"] == 5
    assert callable(bridge_call["progress_callback"])
