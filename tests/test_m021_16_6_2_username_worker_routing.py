from pathlib import Path

from app.interface.desktop.workers.investigation_search_worker import detect_investigation_target
from app.osint.models import OsintTargetType


def test_username_detection():
    target_type, value = detect_investigation_target("example_user")
    assert target_type is OsintTargetType.USERNAME
    assert value == "example_user"


def test_username_osint_routing_present():
    text = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    assert "M021.16.6.2 USERNAME OSINT routing" in text
    assert "OsintTargetType.USERNAME" in text
    assert "osint_enrichment_service.enrich_target" in text
    assert '"osint": osint_result' in text
