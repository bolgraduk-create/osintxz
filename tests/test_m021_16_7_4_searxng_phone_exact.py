from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)


def test_exact_phone_match_accepts_same_digits():
    provider = SearxngPhoneExactOpenWebProvider()
    assert provider._matching_phone_digits(
        "Call +380 67 123 45 67",
        {"380671234567", "0671234567"},
    ) == "380671234567"


def test_exact_phone_match_rejects_neighbor():
    provider = SearxngPhoneExactOpenWebProvider()
    assert provider._matching_phone_digits(
        "Call +380 67 123 45 68",
        {"380671234567", "0671234567"},
    ) is None


def test_local_endpoint_allowed():
    provider = SearxngPhoneExactOpenWebProvider(
        base_url="http://127.0.0.1:8081"
    )
    provider._validate_base_url()


def test_remote_endpoint_requires_opt_in(monkeypatch):
    monkeypatch.delenv("SEARXNG_ALLOW_REMOTE", raising=False)
    provider = SearxngPhoneExactOpenWebProvider(
        base_url="https://example.org"
    )
    try:
        provider._validate_base_url()
    except ValueError:
        return
    raise AssertionError("Remote endpoint unexpectedly allowed.")
