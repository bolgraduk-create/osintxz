from pathlib import Path

from app.osint.capabilities import DiscoveryGoal, capabilities_for_goal
from app.osint.models import OsintTargetType
from app.osint.pivot_policy import OsintPivotPolicy


def test_gravatar_is_default_profile_capability():
    capabilities = capabilities_for_goal(
        DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,
        default_only=True,
    )

    classes = {
        item.connector_class
        for item in capabilities
    }

    assert "GravatarConnector" in classes


def test_email_defaults_include_profile_enrichment():
    goals = OsintPivotPolicy().default_goals(
        OsintTargetType.EMAIL
    )

    assert DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT in goals


def test_service_container_registers_gravatar():
    text = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert "M021.16.5.1 Gravatar runtime registration" in text
    assert "GravatarConnector()" in text
