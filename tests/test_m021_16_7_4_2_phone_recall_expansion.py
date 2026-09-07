from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)
from app.osint.phone_intelligence import PhoneIntelligenceService


def _intel():
    return PhoneIntelligenceService().analyze(
        "+380671234567"
    )


def test_query_plans_include_unquoted_e164_digits():
    plans = (
        SearxngPhoneExactOpenWebProvider
        ._query_plans(_intel())
    )

    assert "380671234567" in [
        item["query"]
        for item in plans
    ]


def test_query_plans_include_national_digits():
    plans = (
        SearxngPhoneExactOpenWebProvider
        ._query_plans(_intel())
    )

    assert "0671234567" in [
        item["query"]
        for item in plans
    ]


def test_query_plan_is_bounded():
    plans = (
        SearxngPhoneExactOpenWebProvider
        ._query_plans(_intel())
    )

    assert 1 <= len(plans) <= 6


def test_exact_verification_rejects_neighbor_number():
    provider = SearxngPhoneExactOpenWebProvider()

    result = provider._matching_phone_digits(
        "Contact +380 67 123 45 68",
        {"380671234567", "0671234567"},
    )

    assert result is None
