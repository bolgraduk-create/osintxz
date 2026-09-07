import pytest

from app.interface.desktop.workers.investigation_search_worker import (
    detect_investigation_target,
)
from app.osint.models import OsintTargetType


@pytest.mark.parametrize(
    ("raw", "target_type", "normalized"),
    [
        ("https://example.com/path", OsintTargetType.URL, "https://example.com/path"),
        ("Example.COM", OsintTargetType.DOMAIN, "example.com"),
        ("alice@example.com", OsintTargetType.EMAIL, "alice@example.com"),
        ("+380 50 123 45 67", OsintTargetType.PHONE, "+380501234567"),
        ("@alice_test", OsintTargetType.USERNAME, "alice_test"),
    ],
)
def test_target_detection(raw, target_type, normalized):
    actual_type, actual_value = detect_investigation_target(raw)
    assert actual_type is target_type
    assert actual_value == normalized


def test_empty_target_rejected():
    with pytest.raises(ValueError):
        detect_investigation_target(" ")
