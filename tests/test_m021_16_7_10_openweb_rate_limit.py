from app.osint.open_web.contracts import (
    OpenWebProviderInfo,
    OpenWebQuery,
    OpenWebResult,
    OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import OpenWebProviderRegistry
from app.osint.open_web.service import OpenWebDiscoveryService
from app.osint.models import OsintTargetType


class RateLimitedProvider(OpenWebProvider):
    def __init__(self):
        self._info = OpenWebProviderInfo(
            name="rate_limited_test",
            display_name="Rate Limited Test",
            supported_targets=frozenset({OsintTargetType.PHONE}),
            passive=True,
            public_data_only=True,
            requires_credentials=False,
            default_enabled=True,
            priority=1,
        )

    @property
    def info(self):
        return self._info

    def search(self, query):
        return OpenWebResult(
            provider=self.info.name,
            status=OpenWebStatus.FAILED,
            error="Client error '429 Too Many Requests'",
            metadata={"source": "test"},
        )


def test_rate_limit_becomes_retryable_partial():
    registry = OpenWebProviderRegistry()
    registry.register(RateLimitedProvider())

    service = OpenWebDiscoveryService(registry=registry)

    response = service.discover(
        OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value="+380631234567",
        )
    )

    assert len(response.results) == 1
    result = response.results[0]

    assert result.status is OpenWebStatus.PARTIAL
    assert result.metadata["rate_limited"] is True
    assert result.metadata["retryable"] is True
    assert "Retry later" in (result.error or "")
