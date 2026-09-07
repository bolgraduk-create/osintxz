from __future__ import annotations

from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    EnrichmentExecutionStatus,
    OsintEnrichmentExecutionService,
)
from app.osint.models import OsintTargetType
from app.osint.pipeline import OsintPipeline
from app.osint.pivot_policy import (
    PivotDecisionCode,
    PivotKey,
    PivotTraversalState,
)
from app.osint.result import OsintFinding, OsintResult, ResultStatus


def make_connector_class(class_name: str):
    return type(class_name, (), {})


def make_connector(
    *,
    class_name: str,
    name: str,
    supported_targets,
    result: OsintResult | None = None,
    raises: Exception | None = None,
):
    cls = make_connector_class(class_name)
    connector = cls()
    connector.name = name
    connector.supported_targets = set(supported_targets)

    def execute(request):
        if raises is not None:
            raise raises
        if result is not None:
            return result
        return OsintResult(connector=name, status=ResultStatus.SUCCESS)

    connector.execute = execute
    return connector


class StubRegistry:
    def __init__(self, connectors) -> None:
        self._items = {connector.name.lower(): connector for connector in connectors}

    def all(self):
        return list(self._items.values())

    def get(self, connector_name):
        return self._items.get(connector_name.lower())

    def supported(self, target_type):
        return [
            item
            for item in self._items.values()
            if target_type in item.supported_targets
        ]

    def names(self):
        return sorted(self._items)


class StubManager:
    def __init__(self, connectors) -> None:
        self.registry = StubRegistry(connectors)


def service(connectors):
    return OsintEnrichmentExecutionService(
        pipeline=OsintPipeline(StubManager(connectors))
    )


def username_connectors():
    maigret = make_connector(
        class_name="MaigretConnector",
        name="Maigret",
        supported_targets={OsintTargetType.USERNAME},
        result=OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="example_user",
                    url="https://example.test/example_user",
                    source="example.test",
                )
            ],
        ),
    )
    sherlock = make_connector(
        class_name="SherlockConnector",
        name="Sherlock",
        supported_targets={OsintTargetType.USERNAME},
        result=OsintResult(connector="Sherlock", status=ResultStatus.SUCCESS),
    )
    return maigret, sherlock


def test_executes_only_connectors_selected_by_router() -> None:
    maigret, sherlock = username_connectors()
    socialscan = make_connector(
        class_name="SocialScanConnector",
        name="SocialScan",
        supported_targets={OsintTargetType.USERNAME},
    )
    nmap = make_connector(
        class_name="NmapConnector",
        name="Nmap",
        supported_targets={OsintTargetType.USERNAME},
    )

    result = service([maigret, sherlock, socialscan, nmap]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert result.status is EnrichmentExecutionStatus.PARTIAL
    assert [r.capability.display_name for r in result.records] == ["Maigret", "Sherlock", "User Scanner", "SocialScan"]
    assert result.unavailable_connectors == 1  # User Scanner is not in this runtime.
    assert not any(r.connector == "Nmap" for r in result.results)


def test_runtime_name_is_resolved_by_connector_class_not_display_name() -> None:
    crtsh = make_connector(
        class_name="CrtShConnector",
        name="crtsh",
        supported_targets={OsintTargetType.DOMAIN},
    )
    subfinder = make_connector(
        class_name="SubfinderConnector",
        name="Subfinder",
        supported_targets={OsintTargetType.DOMAIN},
    )

    result = service([crtsh, subfinder]).execute(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        goal=DiscoveryGoal.DOMAIN_DISCOVERY,
        depth=0,
        entity_identity="entity:domain:1",
        state=PivotTraversalState(),
    )

    by_display = {r.capability.display_name: r for r in result.records}
    assert by_display["crt.sh"].runtime_connector_name == "crtsh"
    assert by_display["crt.sh"].result.connector == "crtsh"


def test_missing_runtime_connector_becomes_not_available_not_exception() -> None:
    maigret, _ = username_connectors()

    result = service([maigret]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert result.status is EnrichmentExecutionStatus.PARTIAL
    assert result.successful_connectors == 1
    assert result.unavailable_connectors == 3


def test_one_connector_exception_isolated_by_existing_pipeline() -> None:
    maigret, _ = username_connectors()
    sherlock = make_connector(
        class_name="SherlockConnector",
        name="Sherlock",
        supported_targets={OsintTargetType.USERNAME},
        raises=RuntimeError("simulated connector failure"),
    )

    result = service([maigret, sherlock]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert result.status is EnrichmentExecutionStatus.PARTIAL
    assert result.successful_connectors == 1
    assert result.failed_connectors == 1


def test_all_unavailable_returns_failed_data_result_not_exception() -> None:
    result = service([]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert result.status is EnrichmentExecutionStatus.FAILED
    assert result.unavailable_connectors == 4


def test_disallowed_pivot_is_skipped_and_not_marked_visited() -> None:
    state = PivotTraversalState()
    result = service([]).execute(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:phone:1",
        state=state,
    )

    assert result.status is EnrichmentExecutionStatus.SKIPPED
    assert result.route.decision.code is PivotDecisionCode.UNSUPPORTED_GOAL
    assert state.visited == set()


def test_allowed_attempt_is_marked_visited_even_if_runtime_tools_missing() -> None:
    state = PivotTraversalState()
    result = service([]).execute(
        target_type=OsintTargetType.USERNAME,
        value="@Example_User",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=state,
    )

    assert result.status is EnrichmentExecutionStatus.FAILED
    key = PivotKey.build(
        OsintTargetType.USERNAME,
        "example_user",
        DiscoveryGoal.ACCOUNT_DISCOVERY,
    )
    assert key in state.visited


def test_second_same_normalized_pivot_is_skipped_by_visited_guard() -> None:
    maigret, sherlock = username_connectors()
    svc = service([maigret, sherlock])
    state = PivotTraversalState()

    first = svc.execute(
        target_type=OsintTargetType.USERNAME,
        value="@Example_User",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=state,
    )
    second = svc.execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=1,
        entity_identity="entity:username:1",
        state=state,
    )

    assert first.status is EnrichmentExecutionStatus.PARTIAL
    assert first.unavailable_connectors == 2
    assert second.status is EnrichmentExecutionStatus.SKIPPED
    assert second.route.decision.code is PivotDecisionCode.ALREADY_VISITED


def test_execution_options_and_case_id_reach_connector_request() -> None:
    captured = {}
    connector = make_connector(
        class_name="PhoneInfogaConnector",
        name="PhoneInfoga",
        supported_targets={OsintTargetType.PHONE},
    )

    def execute(request):
        captured["request"] = request
        return OsintResult(connector="PhoneInfoga", status=ResultStatus.SUCCESS)

    connector.execute = execute

    result = service([connector]).execute(
        target_type=OsintTargetType.PHONE,
        value="+380671234567",
        goal=DiscoveryGoal.PHONE_ENRICHMENT,
        depth=0,
        entity_identity="entity:phone:1",
        state=PivotTraversalState(),
        case_id="case-123",
        timeout=42,
        use_cache=False,
        save_raw_output=True,
        include_metadata=False,
        include_related=False,
    )

    assert result.status is EnrichmentExecutionStatus.PARTIAL
    assert result.unavailable_connectors == 1  # LocalPhone is absent in this stub registry.
    request = captured["request"]
    assert request.target.case_id == "case-123"
    assert request.timeout == 42
    assert request.use_cache is False
    assert request.save_raw_output is True
    assert request.include_metadata is False
    assert request.include_related is False


def test_boundary_adds_capability_provenance_without_overwrite() -> None:
    maigret = make_connector(
        class_name="MaigretConnector",
        name="Maigret",
        supported_targets={OsintTargetType.USERNAME},
        result=OsintResult(
            connector="Maigret",
            status=ResultStatus.SUCCESS,
            metadata={"capability_module": "connector-owned-value"},
        ),
    )
    sherlock = make_connector(
        class_name="SherlockConnector",
        name="Sherlock",
        supported_targets={OsintTargetType.USERNAME},
    )

    result = service([maigret, sherlock]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    by_name = {r.connector: r for r in result.results}
    assert by_name["Maigret"].metadata["capability_module"] == "connector-owned-value"
    assert "discovery_goals" in by_name["Maigret"].metadata
    assert by_name["Sherlock"].metadata["capability_module"] == "sherlock_connector"


def test_total_findings_aggregates_across_connector_results() -> None:
    maigret, _ = username_connectors()
    sherlock = make_connector(
        class_name="SherlockConnector",
        name="Sherlock",
        supported_targets={OsintTargetType.USERNAME},
        result=OsintResult(
            connector="Sherlock",
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(category="account", value="example_user", source="one"),
                OsintFinding(category="account", value="example_user", source="two"),
            ],
        ),
    )

    result = service([maigret, sherlock]).execute(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="entity:username:1",
        state=PivotTraversalState(),
    )

    assert result.total_findings == 3


def test_execute_defaults_keeps_domain_goals_independent() -> None:
    crtsh = make_connector(
        class_name="CrtShConnector",
        name="crtsh",
        supported_targets={OsintTargetType.DOMAIN},
    )
    subfinder = make_connector(
        class_name="SubfinderConnector",
        name="Subfinder",
        supported_targets={OsintTargetType.DOMAIN},
    )
    commoncrawl = make_connector(
        class_name="CommonCrawlConnector",
        name="commoncrawl",
        supported_targets={OsintTargetType.DOMAIN},
    )

    results = service([crtsh, subfinder, commoncrawl]).execute_defaults(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
        depth=0,
        entity_identity="entity:domain:1",
        state=PivotTraversalState(),
    )

    assert len(results) == 2
    assert {r.route.goal for r in results} == {
        DiscoveryGoal.DOMAIN_DISCOVERY,
        DiscoveryGoal.HISTORICAL_WEB,
    }

    domain_result = next(r for r in results if r.route.goal is DiscoveryGoal.DOMAIN_DISCOVERY)
    historical_result = next(r for r in results if r.route.goal is DiscoveryGoal.HISTORICAL_WEB)

    assert domain_result.successful_connectors == 2
    assert historical_result.successful_connectors == 1
    assert historical_result.status is EnrichmentExecutionStatus.PARTIAL
