from app.osint.open_web.providers.gdelt_phone_exact import (
    GdeltPhoneExactOpenWebProvider,
)


def test_exact_match_accepts_e164_format():
    matched = GdeltPhoneExactOpenWebProvider._matching_phone_digits(
        "Contact: +380 67 123 45 67 today.",
        frozenset({"380671234567", "0671234567"}),
    )
    assert matched == "380671234567"


def test_exact_match_accepts_national_format():
    matched = GdeltPhoneExactOpenWebProvider._matching_phone_digits(
        "Телефон: 067 123 45 67.",
        frozenset({"380671234567", "0671234567"}),
    )
    assert matched == "0671234567"


def test_similar_but_different_phone_is_rejected():
    matched = GdeltPhoneExactOpenWebProvider._matching_phone_digits(
        "Contact: +380 67 123 45 68.",
        frozenset({"380671234567", "0671234567"}),
    )
    assert matched is None


def test_gdelt_query_is_exact_phrase_or_block():
    query = GdeltPhoneExactOpenWebProvider._build_gdelt_query(
        ("+380671234567", "+380 67 123 4567")
    )
    assert query.startswith("(")
    assert '"+380671234567"' in query
    assert " OR " in query
