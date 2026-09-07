from __future__ import annotations

from dataclasses import replace

import pytest

from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    NetworkMode,
    OSINT_CAPABILITY_CATALOG,
)
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter


def _route():
    return OsintCapabilityRouter().route(
        target_type=OsintTargetType.USERNAME,
        value="example_user",
        goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        depth=0,
        entity_identity="test:username",
        state=PivotTraversalState(),
    )


def test_account_discovery_includes_passive_support():
    route = _route()

    classes = {
        item.connector_class
        for item in route.connectors
    }

    assert "SherlockConnector" in classes
    assert "MaigretConnector" in classes
    assert "SocialScanConnector" in classes
    assert "UserScannerConnector" in classes


def test_catalog_rejects_active_default_connector():
    socialscan = OSINT_CAPABILITY_CATALOG[
        "socialscan_connector"
    ]

    with pytest.raises(
        ValueError,
        match="active connectors cannot be automatic enrichment defaults",
    ):
        replace(
            socialscan,
            network_mode=NetworkMode.ACTIVE,
        )


def test_account_discovery_rejects_active_support():
    router = OsintCapabilityRouter()

    socialscan = OSINT_CAPABILITY_CATALOG[
        "socialscan_connector"
    ]

    active_copy = replace(
        socialscan,
        default_enabled=False,
        network_mode=NetworkMode.ACTIVE,
    )

    assert (
        router._network_mode_allowed_for_goal(
            capability=active_copy,
            goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        )
        is False
    )


def test_account_discovery_accepts_passive_support():
    router = OsintCapabilityRouter()

    socialscan = OSINT_CAPABILITY_CATALOG[
        "socialscan_connector"
    ]

    assert (
        socialscan.disposition
        is ConnectorDisposition.SUPPORT
    )

    assert (
        router._network_mode_allowed_for_goal(
            capability=socialscan,
            goal=DiscoveryGoal.ACCOUNT_DISCOVERY,
        )
        is True
    )


def test_email_registration_rejects_active_support():
    router = OsintCapabilityRouter()

    socialscan = OSINT_CAPABILITY_CATALOG[
        "socialscan_connector"
    ]

    active_copy = replace(
        socialscan,
        default_enabled=False,
        network_mode=NetworkMode.ACTIVE,
    )

    assert (
        router._network_mode_allowed_for_goal(
            capability=active_copy,
            goal=DiscoveryGoal.EMAIL_REGISTRATION,
        )
        is False
    )
