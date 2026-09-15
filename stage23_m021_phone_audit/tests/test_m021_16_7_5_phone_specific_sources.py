from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)
from app.osint.phone_intelligence import PhoneIntelligenceService


def _provider():
    return TargetedPhonePublicSourcesProvider()


def _intel():
    return PhoneIntelligenceService().analyze("+380671234567")


def test_query_plans_are_source_targeted():
    plans = _provider()._build_query_plans(_intel())
    assert plans
    assert all("site:" in item["query"] for item in plans)


def test_rule_allowlist_accepts_subdomain():
    rule = _provider()._rule_for_url(
        "https://www.dzo.com.ua/contracts/123"
    )
    assert rule is not None
    assert rule.name == "dzo"


def test_rule_allowlist_rejects_lookalike():
    rule = _provider()._rule_for_url(
        "https://dzo.com.ua.evil.example/"
    )
    assert rule is None


def test_exact_phone_gate_rejects_neighbor():
    matched = _provider()._matching_phone_digits(
        "Contact +380 67 123 45 68",
        {"380671234567", "0671234567"},
    )
    assert matched is None


def test_source_tiers_are_bounded():
    provider = _provider()
    for rule in provider.rules:
        assert 0.0 <= rule.confidence <= 1.0
        assert 0.0 <= rule.reliability <= 1.0
