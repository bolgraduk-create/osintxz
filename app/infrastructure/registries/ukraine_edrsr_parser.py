"""Streaming parser for the official EDRSR yearly ZIP CSV layout.

Official documentation states that the archive contains tab-separated UTF-8 CSV
files with quoted strings. The main file is documents.csv and reference tables
include courts, instances, judgment forms, justice kinds, regions and case
categories.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Iterator, TextIO

from app.repositories.registry_ua_edrsr_repository import normalize_case_number


DOCUMENTS_FILENAME = "documents.csv"
REFERENCE_FILENAMES = frozenset({
    "cause_categories.csv",
    "courts.csv",
    "instances.csv",
    "judgment_forms.csv",
    "justice_kinds.csv",
    "regions.csv",
})


@dataclass(frozen=True, slots=True)
class UaEdrsrReferenceData:
    categories: dict[str, str]
    courts: dict[str, dict[str, str]]
    instances: dict[str, str]
    judgments: dict[str, str]
    justice_kinds: dict[str, str]
    regions: dict[str, str]

    @classmethod
    def empty(cls) -> "UaEdrsrReferenceData":
        return cls({}, {}, {}, {}, {}, {})


def _text_stream(stream: BinaryIO | TextIO):
    if isinstance(stream, io.TextIOBase):
        return stream, False
    # utf-8-sig tolerates a BOM while preserving normal UTF-8 behavior.
    return io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""), True


def _reader(stream: BinaryIO | TextIO) -> tuple[csv.DictReader, TextIO, bool]:
    text, wrapped = _text_stream(stream)
    reader = csv.DictReader(text, delimiter="\t", quotechar='"')
    return reader, text, wrapped


def _clean(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_int(value: object) -> int | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _parse_datetime(value: object) -> datetime | None:
    text = _clean(value)
    if text is None:
        return None
    normalized = re.sub(r"\s+", " ", text)
    # The official exports historically use ordinary SQL timestamps. Keep the
    # parser conservative and accept ISO variants without inventing a timezone.
    for candidate in (normalized, normalized.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def parse_reference_file(
    filename: str,
    stream: BinaryIO | TextIO,
) -> dict[str, object]:
    """Parse one official lookup file into a compact mapping."""
    name = (filename or "").strip().casefold()
    if name not in REFERENCE_FILENAMES:
        raise ValueError(f"Unsupported EDRSR reference file: {filename}")

    reader, text, wrapped = _reader(stream)
    try:
        if name == "courts.csv":
            result: dict[str, object] = {}
            for row in reader:
                code = _clean(row.get("court_code"))
                if code:
                    result[code] = {
                        "name": _clean(row.get("name")) or "",
                        "instance_code": _clean(row.get("instance_code")) or "",
                        "region_code": _clean(row.get("region_code")) or "",
                    }
            return result

        key_field = {
            "cause_categories.csv": "category_code",
            "instances.csv": "instance_code",
            "judgment_forms.csv": "judgment_code",
            "justice_kinds.csv": "justice_kind",
            "regions.csv": "region_code",
        }[name]
        result = {}
        for row in reader:
            key = _clean(row.get(key_field))
            label = _clean(row.get("name"))
            if key and label:
                result[key] = label
        return result
    finally:
        if wrapped:
            text.detach()


def build_reference_data(files: dict[str, BinaryIO | TextIO]) -> UaEdrsrReferenceData:
    normalized = {str(name).casefold(): stream for name, stream in files.items()}
    return UaEdrsrReferenceData(
        categories=parse_reference_file("cause_categories.csv", normalized["cause_categories.csv"])
        if "cause_categories.csv" in normalized else {},
        courts=parse_reference_file("courts.csv", normalized["courts.csv"])
        if "courts.csv" in normalized else {},
        instances=parse_reference_file("instances.csv", normalized["instances.csv"])
        if "instances.csv" in normalized else {},
        judgments=parse_reference_file("judgment_forms.csv", normalized["judgment_forms.csv"])
        if "judgment_forms.csv" in normalized else {},
        justice_kinds=parse_reference_file("justice_kinds.csv", normalized["justice_kinds.csv"])
        if "justice_kinds.csv" in normalized else {},
        regions=parse_reference_file("regions.csv", normalized["regions.csv"])
        if "regions.csv" in normalized else {},
    )


def iter_documents(
    stream: BinaryIO | TextIO,
    *,
    dataset_year: int,
    generation: str,
    references: UaEdrsrReferenceData | None = None,
    source_dataset_id: str | None = None,
    source_resource_id: str | None = None,
    source_modified_at: str | None = None,
    source_hash: str | None = None,
) -> Iterator[dict]:
    """Yield normalized SQLAlchemy/COPY-ready decision rows."""
    refs = references or UaEdrsrReferenceData.empty()
    reader, text, wrapped = _reader(stream)
    try:
        required = {"doc_id", "cause_num", "court_code", "judgment_code", "justice_kind"}
        fieldnames = {str(item or "").strip() for item in (reader.fieldnames or [])}
        missing = required - fieldnames
        if missing:
            raise ValueError(
                "EDRSR documents.csv is missing required fields: "
                + ", ".join(sorted(missing))
            )

        for raw in reader:
            doc_id = _parse_int(raw.get("doc_id"))
            if doc_id is None:
                continue

            court_code = _clean(raw.get("court_code"))
            judgment_code = _clean(raw.get("judgment_code"))
            justice_kind = _clean(raw.get("justice_kind"))
            category_code = _clean(raw.get("category_code"))
            cause_num = _clean(raw.get("cause_num"))
            court = refs.courts.get(court_code or "", {})
            instance_code = str(court.get("instance_code") or "") if court else ""
            region_code = str(court.get("region_code") or "") if court else ""

            yield {
                "dataset_year": int(dataset_year),
                "generation": generation,
                "doc_id": doc_id,
                "court_code": court_code,
                "court_name": _clean(court.get("name")) if court else None,
                "instance_name": refs.instances.get(instance_code) or None,
                "region_name": refs.regions.get(region_code) or None,
                "judgment_code": judgment_code,
                "judgment_name": refs.judgments.get(judgment_code or "") or None,
                "justice_kind": justice_kind,
                "justice_kind_name": refs.justice_kinds.get(justice_kind or "") or None,
                "category_code": category_code,
                "category_name": refs.categories.get(category_code or "") or None,
                "cause_num": cause_num,
                "cause_num_normalized": normalize_case_number(cause_num),
                "adjudication_date": _parse_datetime(raw.get("adjudication_date")),
                "receipt_date": _parse_datetime(raw.get("receipt_date")),
                "judge": _clean(raw.get("judge")),
                "doc_url": _clean(raw.get("doc_url")),
                "status": _parse_int(raw.get("status")),
                "date_publ": _parse_datetime(raw.get("date_publ")),
                "source_dataset_id": source_dataset_id,
                "source_resource_id": source_resource_id,
                "source_modified_at": source_modified_at,
                "source_hash": source_hash,
                "raw_reference": f"ua-edrsr:{doc_id}",
            }
    finally:
        if wrapped:
            text.detach()
