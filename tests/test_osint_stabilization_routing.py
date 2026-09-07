import pytest

from app.interface.desktop.workers.investigation_search_worker import detect_investigation_target
from app.osint.capabilities import DiscoveryGoal, NetworkMode
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import PivotTraversalState
from app.osint.pivot_router import OsintCapabilityRouter


@pytest.mark.parametrize("raw, expected", [
    ("8.8.8.8", "8.8.8.8"),
    ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
    ("::1", "::1"),
])
def test_ip_detection_precedes_username(raw, expected):
    assert detect_investigation_target(raw) == (OsintTargetType.IP, expected)


def test_parenthesized_national_phone_preserves_unknown_country():
    assert detect_investigation_target("(063) 287-44-04") == (
        OsintTargetType.PHONE, "0632874404"
    )


def test_email_registration_includes_passive_support_without_credentials():
    route = OsintCapabilityRouter().route(
        target_type=OsintTargetType.EMAIL, value="alice@example.org",
        goal=DiscoveryGoal.EMAIL_REGISTRATION, depth=0,
        entity_identity="email:alice", state=PivotTraversalState(),
    )
    assert {"Holehe", "SocialScan"} <= {c.display_name for c in route.connectors}
    assert all(not c.requires_account and not c.requires_api_key for c in route.connectors)
    assert all(c.network_mode in {NetworkMode.PASSIVE, NetworkMode.PASSIVE_REMOTE}
               for c in route.connectors)
