from app.osint.phone_intelligence import PhoneIntelligenceService


def test_variant_generator_is_bounded_and_exact():
    variants = PhoneIntelligenceService.build_search_variants(
        raw="+380 67 123 45 67",
        e164="+380671234567",
        international="+380 67 123 4567",
        national="067 123 4567",
    )
    assert '"+380671234567"' in variants
    assert '"380671234567"' in variants
    assert len(variants) <= 6
    assert all(item.startswith('"') and item.endswith('"') for item in variants)


def test_variant_generator_does_not_infer_country():
    variants = PhoneIntelligenceService.build_search_variants(
        raw="0671234567",
        e164=None,
        international=None,
        national=None,
    )
    assert variants == ()


def test_service_availability_returns_bool():
    assert isinstance(PhoneIntelligenceService.available(), bool)
