from io import BytesIO

from app.infrastructure.registries.ukraine_edr_parser import UaEdrXmlParser


class _TinyChunkStream(BytesIO):
    def read(self, size=-1):
        if size is None or size < 0:
            size = 3
        return super().read(min(size, 3))


def test_invalid_numeric_xml_character_reference_is_repaired_not_fatal():
    xml = (
        b'<?xml version="1.0" encoding="utf-8"?><DATA><SUBJECT>'
        b'<RECORD>fop-1</RECORD>'
        b'<NAME>IVAN&#11; IVAN&#x0B; IVAN</NAME>'
        b'<REGISTRATION>ok&#9;tab</REGISTRATION>'
        b'</SUBJECT></DATA>'
    )
    parser = UaEdrXmlParser()
    rows = list(parser.iter_subjects(_TinyChunkStream(xml), subject_kind="sole_trader"))

    assert len(rows) == 1
    assert rows[0].name == "IVAN  IVAN  IVAN"
    assert "tab" in (rows[0].registration_info or "")
    assert parser.last_invalid_reference_count == 2
    assert parser.last_invalid_control_byte_count == 0


def test_literal_xml10_forbidden_control_byte_is_repaired_not_fatal():
    xml = (
        b'<?xml version="1.0" encoding="utf-8"?><DATA><SUBJECT>'
        b'<RECORD>fop-2</RECORD><NAME>TEST\x0b PERSON</NAME>'
        b'</SUBJECT></DATA>'
    )
    parser = UaEdrXmlParser()
    rows = list(parser.iter_subjects(BytesIO(xml), subject_kind="sole_trader"))

    assert len(rows) == 1
    assert rows[0].name == "TEST  PERSON"
    assert parser.last_invalid_control_byte_count == 1


def test_valid_high_unicode_numeric_reference_is_preserved():
    xml = (
        b'<?xml version="1.0" encoding="utf-8"?><DATA><SUBJECT>'
        b'<RECORD>1</RECORD><NAME>TEST &#x1F600;</NAME>'
        b'</SUBJECT></DATA>'
    )
    parser = UaEdrXmlParser()
    row = next(parser.iter_subjects(BytesIO(xml), subject_kind="company"))
    assert row.name == "TEST \U0001f600"
    assert parser.last_invalid_reference_count == 0
