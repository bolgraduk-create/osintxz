from __future__ import annotations

from io import BytesIO

from app.infrastructure.registries.ukraine_edrsr_parser import (
    UaEdrsrReferenceData,
    iter_documents,
    parse_reference_file,
)


def test_parser_reads_official_tab_separated_documents_and_lookups():
    courts = parse_reference_file(
        "courts.csv",
        BytesIO(
            (
                "court_code\tname\tinstance_code\tregion_code\n"
                "5014\tГосподарський суд Луганської області\t1\t44\n"
            ).encode("utf-8")
        ),
    )
    refs = UaEdrsrReferenceData(
        categories={"4047": "Інший майновий спір"},
        courts=courts,
        instances={"1": "Перша інстанція"},
        judgments={"5": "Рішення"},
        justice_kinds={"3": "Господарське"},
        regions={"44": "Луганська область"},
    )
    raw = (
        "doc_id\tcourt_code\tjudgment_code\tjustice_kind\tcategory_code\tcause_num\t"
        "adjudication_date\treceipt_date\tjudge\tdoc_url\tstatus\tdate_publ\n"
        "195\t5014\t5\t3\t4047\t19/273\t2006-06-01 00:00:00\t"
        "2006-06-05 00:00:00\tБойченко К.І.\thttp://example.test/195.html\t1\t"
        "2007-08-22 00:00:00\n"
    ).encode("utf-8")
    rows = list(
        iter_documents(
            BytesIO(raw),
            dataset_year=2006,
            generation="g1",
            references=refs,
            source_dataset_id="dataset",
            source_resource_id="resource",
            source_hash="abc",
        )
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["doc_id"] == 195
    assert row["cause_num_normalized"] == "19/273"
    assert row["court_name"] == "Господарський суд Луганської області"
    assert row["judgment_name"] == "Рішення"
    assert row["justice_kind_name"] == "Господарське"
    assert row["category_name"] == "Інший майновий спір"
    assert row["raw_reference"] == "ua-edrsr:195"


def test_documents_parser_rejects_unknown_schema():
    raw = b"doc_id\tcause_num\n1\t1/1\n"
    try:
        list(iter_documents(BytesIO(raw), dataset_year=2026, generation="g"))
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("schema drift must fail closed")
