from __future__ import annotations

import hashlib
import requests

from app.osint.connectors.gravatar_connector import GravatarConnector
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
from app.osint.result import ResultStatus


class _Response:
    def __init__(self, *, status_code: int, data=None, text: str = ""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


def _request(email: str) -> ConnectorRequest:
    return ConnectorRequest(
        target=OsintTarget(
            target_type=OsintTargetType.EMAIL,
            value=email,
        ),
        timeout=10,
    )


def test_gravatar_hash_uses_trim_lowercase_sha256():
    expected = hashlib.sha256(
        b"user.name@example.com"
    ).hexdigest()

    assert (
        GravatarConnector.email_hash(
            "  User.Name@Example.com "
        )
        == expected
    )


def test_404_is_clean_success_with_zero_findings(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _Response(
            status_code=404,
            data={},
        ),
    )

    result = GravatarConnector().execute(
        _request("none@example.com")
    )

    assert result.status is ResultStatus.SUCCESS
    assert result.total_findings == 0
    assert result.metadata["profile_found"] is False


def test_profile_and_verified_accounts_become_findings(monkeypatch):
    data = {
        "display_name": "Example User",
        "profile_url": "https://gravatar.com/example",
        "avatar_url": "https://0.gravatar.com/avatar/hash",
        "company": "Example Co",
        "verified_accounts": [
            {
                "service_type": "github",
                "service_label": "GitHub",
                "url": "https://github.com/example",
                "is_hidden": False,
            },
            {
                "service_type": "twitter",
                "service_label": "Twitter",
                "url": "https://twitter.com/example",
                "is_hidden": False,
            },
        ],
    }

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _Response(
            status_code=200,
            data=data,
        ),
    )

    result = GravatarConnector().execute(
        _request("user@example.com")
    )

    assert result.status is ResultStatus.SUCCESS
    assert result.total_findings == 3
    assert [f.category for f in result.findings].count("account") == 1
    assert [f.category for f in result.findings].count("url") == 2
    assert result.metadata["verified_accounts_found"] == 2


def test_descriptive_fields_stay_metadata(monkeypatch):
    data = {
        "display_name": "Example User",
        "profile_url": "https://gravatar.com/example",
        "location": "Somewhere",
        "company": "Example Co",
        "verified_accounts": [],
    }

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _Response(
            status_code=200,
            data=data,
        ),
    )

    result = GravatarConnector().execute(
        _request("user@example.com")
    )

    assert result.total_findings == 1
    assert result.findings[0].category == "account"
    assert result.findings[0].metadata["company"] == "Example Co"
