from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.interface.desktop.workers.investigation_search_worker import (
    InvestigationSearchWorker,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState


class FakeOneShotEnrichment:
    def __init__(self):
        self.calls = []

    def enrich_target(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            marker="one-shot",
            executions=[],
            persistence=[],
        )


class FakeRecursiveService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def enrich(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeOpenWebService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def enrich(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


class FakeOpenWebRecursive:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def expand(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def fake_open_web_result():
    return SimpleNamespace(
        query=SimpleNamespace(
            depth=0,
        ),
        persistence=[],
    )


def build_container(*, recursive_result):
    one_shot = FakeOneShotEnrichment()
    open_web_result = fake_open_web_result()
    open_web = FakeOpenWebService(open_web_result)
    bridge_result = SimpleNamespace(
        candidates_discovered=0,
        recursive_targets_processed=0,
        recursion=None,
    )
    bridge = FakeOpenWebRecursive(bridge_result)
    recursive = FakeRecursiveService(recursive_result)

    container = SimpleNamespace(
        osint_enrichment_service=one_shot,
        osint_recursive_enrichment_service=recursive,
        open_web_enrichment_service=open_web,
        open_web_recursive_pivot_service=bridge,
    )

    return container, one_shot, recursive, open_web, bridge, bridge_result


def test_recursive_checkbox_starts_root_recursive_service_and_reuses_state():
    state = PivotTraversalState()
    root_run = SimpleNamespace(
        marker="root-run",
        executions=[],
        persistence=[],
        depth=0,
    )
    recursive_result = SimpleNamespace(
        runs=[root_run],
        state=state,
        targets_processed=2,
        candidates_discovered=1,
        candidates_enqueued=1,
        stop_reason=SimpleNamespace(value="queue_exhausted"),
    )

    (
        container,
        one_shot,
        recursive,
        _open_web,
        bridge,
        bridge_result,
    ) = build_container(
        recursive_result=recursive_result,
    )

    worker = InvestigationSearchWorker(
        container=container,
        case_id=uuid4(),
        raw_target="example.com",
        recursive=True,
    )

    payloads = []
    failures = []

    worker.result_ready.connect(payloads.append)
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert len(payloads) == 1

    payload = payloads[0]

    assert payload["osint"] is root_run
    assert payload["recursive"] is recursive_result
    assert payload["open_web_recursive"] is bridge_result

    assert one_shot.calls == []
    assert len(recursive.calls) == 1
    assert len(bridge.calls) == 1

    recursive_call = recursive.calls[0]
    seed = recursive_call["seeds"][0]

    assert seed.target_type is OsintTargetType.DOMAIN
    assert seed.value == "example.com"
    assert recursive_call["seed_depth"] == 0

    # Critical 05R3 contract: Open-Web additions continue inside the SAME
    # traversal state, so visited/pivot/entity budgets remain global.
    assert bridge.calls[0]["state"] is state


def test_non_recursive_search_keeps_existing_one_shot_path():
    recursive_result = SimpleNamespace(
        runs=[],
        state=PivotTraversalState(),
    )

    (
        container,
        one_shot,
        recursive,
        _open_web,
        bridge,
        _bridge_result,
    ) = build_container(
        recursive_result=recursive_result,
    )

    worker = InvestigationSearchWorker(
        container=container,
        case_id=uuid4(),
        raw_target="example.com",
        recursive=False,
    )

    payloads = []
    failures = []

    worker.result_ready.connect(payloads.append)
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert len(payloads) == 1
    assert payloads[0]["osint"].marker == "one-shot"
    assert payloads[0]["recursive"] is None
    assert payloads[0]["open_web_recursive"] is None

    assert len(one_shot.calls) == 1
    assert recursive.calls == []
    assert bridge.calls == []


def test_email_recursive_mode_is_no_longer_artificially_deferred():
    state = PivotTraversalState()
    root_run = SimpleNamespace(
        marker="email-root",
        executions=[],
        persistence=[],
        depth=0,
    )
    recursive_result = SimpleNamespace(
        runs=[root_run],
        state=state,
        targets_processed=1,
        candidates_discovered=0,
        candidates_enqueued=0,
        stop_reason=SimpleNamespace(value="queue_exhausted"),
    )

    (
        container,
        one_shot,
        recursive,
        _open_web,
        bridge,
        _bridge_result,
    ) = build_container(
        recursive_result=recursive_result,
    )

    worker = InvestigationSearchWorker(
        container=container,
        case_id=uuid4(),
        raw_target="alice@example.com",
        recursive=True,
    )

    failures = []
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert one_shot.calls == []
    assert len(recursive.calls) == 1
    assert (
        recursive.calls[0]["seeds"][0].target_type
        is OsintTargetType.EMAIL
    )
    assert len(bridge.calls) == 1


def test_username_recursive_mode_uses_root_bfs():
    state = PivotTraversalState()
    root_run = SimpleNamespace(
        marker="username-root",
        executions=[],
        persistence=[],
        depth=0,
    )
    recursive_result = SimpleNamespace(
        runs=[root_run],
        state=state,
        targets_processed=1,
        candidates_discovered=0,
        candidates_enqueued=0,
        stop_reason=SimpleNamespace(value="queue_exhausted"),
    )

    (
        container,
        one_shot,
        recursive,
        _open_web,
        bridge,
        _bridge_result,
    ) = build_container(
        recursive_result=recursive_result,
    )

    worker = InvestigationSearchWorker(
        container=container,
        case_id=uuid4(),
        raw_target="@alice_user",
        recursive=True,
    )

    failures = []
    worker.failed.connect(failures.append)

    worker.run()

    assert failures == []
    assert one_shot.calls == []
    assert len(recursive.calls) == 1
    assert (
        recursive.calls[0]["seeds"][0].target_type
        is OsintTargetType.USERNAME
    )
    assert len(bridge.calls) == 1
