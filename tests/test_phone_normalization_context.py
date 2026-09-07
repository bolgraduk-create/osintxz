import pytest

from app.osint.connectors.local_phone_connector import LocalPhoneConnector
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
from app.osint.phone_intelligence import PhoneIntelligenceService
from app.osint.result import ResultStatus


@pytest.mark.parametrize("value", ["0632874404", "063 287 44 04", "063-287-4404",
    "(063) 287-44-04", "380632874404", "+380632874404"])
def test_ukraine_context_normalizes_all_input_forms(value):
    result = PhoneIntelligenceService().analyze(value, default_region="UA")
    assert result.valid and result.possible
    assert result.e164 == "+380632874404"
    assert result.metadata()["network_used"] is False
    assert result.metadata()["local_only"] is True


def test_national_number_does_not_assume_ukraine():
    result = PhoneIntelligenceService().analyze("0632874404")
    assert result.e164 is None
    assert result.normalization_status == "ambiguous"
    assert result.search_variants == ()


def test_country_code_without_plus_is_only_a_candidate_without_context():
    result = PhoneIntelligenceService().analyze("380632874404")
    assert result.e164 is None
    assert result.possible_e164_candidates == ("+380632874404",)


def test_other_country_context_is_supported():
    assert PhoneIntelligenceService().analyze("020 7946 0018", default_region="GB").e164 == "+442079460018"


def test_local_phone_ambiguous_is_partial_not_provider_failure():
    result = LocalPhoneConnector().execute(ConnectorRequest(
        OsintTarget(OsintTargetType.PHONE, "0632874404")))
    assert result.status is ResultStatus.PARTIAL
    assert not any(f.category == "phone" for f in result.findings)


def test_local_phone_explicit_context_is_canonical():
    result = LocalPhoneConnector(default_region="UA").execute(ConnectorRequest(
        OsintTarget(OsintTargetType.PHONE, "(063) 287-44-04")))
    assert result.status is ResultStatus.SUCCESS
    assert any(f.category == "phone" and f.value == "+380632874404" for f in result.findings)
