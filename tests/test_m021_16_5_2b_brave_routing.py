from pathlib import Path

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebProviderInfo,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import OpenWebProviderRegistry


class _CredentialedProvider(OpenWebProvider):
    def __init__(self, name: str, available: bool):
        self.available = available
        self._info = OpenWebProviderInfo(
            name=name,
            display_name="Credentialed",
            supported_targets=frozenset(
                {OsintTargetType.EMAIL}
            ),
            passive=True,
            public_data_only=True,
            requires_credentials=True,
            default_enabled=True,
        )

    @property
    def info(self):
        return self._info

    def is_available(self):
        return self.available

    def search(self, query):
        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.SUCCESS,
        )


def test_registry_routes_only_available_credentials():
    registry = OpenWebProviderRegistry()

    registry.register(
        _CredentialedProvider(
            "credentialed_yes",
            True,
        )
    )
    registry.register(
        _CredentialedProvider(
            "credentialed_no",
            False,
        )
    )

    providers = registry.automatic_for(
        OpenWebQuery(
            target_type=OsintTargetType.EMAIL,
            value="target@example.com",
        )
    )

    names = {
        item.info.name
        for item in providers
    }

    assert "credentialed_yes" in names
    assert "credentialed_no" not in names


def test_config_has_brave_secret_setting():
    text = Path(
        "app/core/config.py"
    ).read_text(encoding="utf-8")

    assert (
        "brave_search_api_key: "
        "SecretStr | None = None"
        in text
    )


def test_container_registers_brave_provider():
    text = Path(
        "app/core/service_container.py"
    ).read_text(encoding="utf-8")

    assert (
        "M021.16.5.2B Brave exact-email "
        "Open-Web registration"
        in text
    )
    assert "BraveExactEmailOpenWebProvider" in text
