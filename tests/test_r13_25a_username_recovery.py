from __future__ import annotations

from types import SimpleNamespace

from app.application.investigation_result_consolidation import consolidate_result_rows
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import OsintEnrichmentExecutionService
from app.osint.manager import OsintManager
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.result import OsintFinding, OsintResult, ResultStatus


def _account(source: str, url: str) -> dict:
    return {
        "lane": "Classic OSINT",
        "source": source,
        "service": source,
        "title": "texnobreath",
        "detail": "Account",
        "type": "account",
        "status": "Finding",
        "url": url,
        "seed": "texnobreath",
        "seedType": "username",
        "identifiers": {"username": "texnobreath"},
        "findingMetadata": {
            "registration_confirmed": True,
            "service": source,
        },
        "candidateOnly": False,
        "depth": 0,
    }


def test_same_username_on_different_platforms_stays_separate():
    result = consolidate_result_rows(
        [
            _account("GitHub", "https://github.com/texnobreath"),
            _account("Reddit", "https://www.reddit.com/user/texnobreath"),
            _account("Telegram", "https://t.me/texnobreath"),
        ],
        seeds=[{"kind": "username", "value": "texnobreath"}],
    )

    assert len(result.rows) == 3
    assert len(result.related_accounts or []) == 3
    assert {row["url"] for row in result.rows} == {
        "https://github.com/texnobreath",
        "https://www.reddit.com/user/texnobreath",
        "https://t.me/texnobreath",
    }


def test_same_profile_url_from_two_connectors_is_still_merged():
    first = _account("Sherlock", "https://github.com/texnobreath")
    second = _account("Maigret", "https://github.com/texnobreath")

    result = consolidate_result_rows(
        [first, second],
        seeds=[{"kind": "username", "value": "texnobreath"}],
    )

    assert len(result.rows) == 1
    assert result.rows[0]["corroborationCount"] == 2
    assert result.rows[0]["duplicatesMerged"] == 1


class _Registry:
    def all(self):
        return []


class _Manager:
    registry = _Registry()


class _RecordingExecutionService(OsintEnrichmentExecutionService):
    def __init__(self):
        super().__init__(
            pipeline=SimpleNamespace(manager=_Manager()),
            router=SimpleNamespace(
                policy=SimpleNamespace(
                    limits=SimpleNamespace(max_new_entities=50),
                )
            ),
        )
        self.requests = []

    def _resolve_runtime_connector_name(self, capability):
        return capability.display_name

    def _execute_connector(self, *, runtime_name, capability, request):
        self.requests.append((runtime_name, request.limit))
        return OsintResult(
            connector=runtime_name,
            status=ResultStatus.SUCCESS,
            findings=[
                OsintFinding(
                    category="account",
                    value="texnobreath",
                    source=runtime_name,
                    url=f"https://example.test/{runtime_name.lower()}/texnobreath/{index}",
                )
                for index in range(20)
            ],
        )


def _capability(name: str):
    return SimpleNamespace(
        display_name=name,
        module=f"test.{name}",
        connector_class=f"{name}Connector",
        goals=frozenset({DiscoveryGoal.ACCOUNT_DISCOVERY}),
    )


def test_username_discovery_budget_does_not_stop_after_eight_findings():
    service = _RecordingExecutionService()
    route = SimpleNamespace(
        allowed=True,
        decision=SimpleNamespace(reason="allowed"),
        connectors=tuple(
            _capability(name)
            for name in ("Maigret", "Sherlock", "User Scanner", "SocialScan")
        ),
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
    )
    service.router.route = lambda **kwargs: route

    result = service.execute(
        target_type=OsintTargetType.USERNAME,
        value="texnobreath",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="target:username:texnobreath",
        state=PivotTraversalState(),
        entity_budget=SimpleNamespace(
            remaining=8,
            exhausted=False,
        ),
        finding_limit=8,
    )

    assert len(service.requests) == 4
    assert [limit for _name, limit in service.requests] == [80, 80, 80, 80]
    assert result.total_findings == 80


def test_user_scanner_is_registered_in_runtime_manager():
    manager = OsintManager()
    connector = manager.registry.get("user_scanner")
    assert connector is not None
    assert OsintTargetType.USERNAME in connector.supported_targets
