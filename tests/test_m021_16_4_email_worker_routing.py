from pathlib import Path

from app.interface.desktop.workers.investigation_search_worker import (
    detect_investigation_target,
)
from app.osint.models import OsintTargetType


def test_email_detection_is_preserved():
    target_type, value = detect_investigation_target(
        "User.Name+tag@example.com"
    )
    assert target_type is OsintTargetType.EMAIL
    assert value == "User.Name+tag@example.com"


def test_worker_routes_email_to_existing_osint_service():
    text = Path(
        "app/interface/desktop/workers/investigation_search_worker.py"
    ).read_text(encoding="utf-8")
    assert "M021.16.4 EMAIL routing" in text
    assert "target_type is OsintTargetType.EMAIL" in text
    assert "osint_enrichment_service.enrich_target" in text
    assert '"osint": osint_result' in text
    assert "open_web_enrichment_service.enrich" in text
