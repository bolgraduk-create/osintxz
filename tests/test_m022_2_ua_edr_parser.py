from io import BytesIO

import pytest

from app.infrastructure.registries.ukraine_edr_parser import UaEdrXmlParser


def test_parses_company_subject_from_current_edr_shape():
    xml = b'''<?xml version="1.0" encoding="utf-8"?>
    <DATA><SUBJECT>
      <RECORD>101</RECORD>
      <NAME>TEST COMPANY LLC</NAME>
      <SHORT_NAME>TEST LLC</SHORT_NAME>
      <OPF>LIMITED LIABILITY COMPANY</OPF>
      <EDRPOU>12345678</EDRPOU>
      <STAN>registered</STAN>
      <REGISTRATION>2024-01-01, 123</REGISTRATION>
      <FOUNDERS><FOUNDER><NAME>Founder One</NAME></FOUNDER></FOUNDERS>
    </SUBJECT></DATA>'''
    rows = list(UaEdrXmlParser().iter_subjects(BytesIO(xml), subject_kind="company"))
    assert len(rows) == 1
    row = rows[0]
    assert row.record_id == "101"
    assert row.registration_id == "12345678"
    assert row.name_normalized == "TEST COMPANY LLC"
    assert row.legal_form == "LIMITED LIABILITY COMPANY"
    assert "Founder One" in row.metadata["founders"]


def test_parses_sole_trader_without_inventing_tax_id():
    xml = '''<?xml version="1.0" encoding="utf-8"?>
    <DATA><SUBJECT>
      <RECORD>fop-77</RECORD>
      <NAME>ІВАНЕНКО ІВАН ІВАНОВИЧ</NAME>
      <STAN>зареєстровано</STAN>
      <REGISTRATION>2025-03-01, 999</REGISTRATION>
      <FARMER>так</FARMER>
    </SUBJECT></DATA>'''.encode("utf-8")
    row = next(UaEdrXmlParser().iter_subjects(BytesIO(xml), subject_kind="sole_trader"))
    assert row.name == "ІВАНЕНКО ІВАН ІВАНОВИЧ"
    assert row.registration_id is None
    assert row.family_farm is True


def test_rejects_xml_doctype_and_entities():
    xml = b'''<?xml version="1.0"?><!DOCTYPE x [<!ENTITY y "boom">]><DATA/>'''
    with pytest.raises(ValueError, match="Unsafe XML"):
        list(UaEdrXmlParser().iter_subjects(BytesIO(xml), subject_kind="company"))
