"""Bounded streaming parser for official Ukraine EDR UO/FOP XML exports."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import io
import json
import re
from typing import BinaryIO, Iterator
import xml.etree.ElementTree as ET

from app.registry_intelligence.normalization import normalize_ua_edr_name


_MAX_SECURITY_PREFIX = 262_144
_MAX_TEXT_FIELD = 32_000
_RELATION_TAGS = {
    "FOUNDERS",
    "BENEFICIARIES",
    "SIGNERS",
    "BRANCHES",
    "MEMBERS",
    "ASSIGNEES",
    "PREDECESSORS",
    "EXECUTIVE_POWER",
}


def _local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1].upper()


def _bounded_text(element: ET.Element, limit: int = _MAX_TEXT_FIELD) -> str | None:
    text = " ".join(part.strip() for part in element.itertext() if part and part.strip())
    if not text:
        return None
    return text[:limit]


class _PrefixedReader:
    def __init__(self, prefix: bytes, source: BinaryIO) -> None:
        self._prefix = io.BytesIO(prefix)
        self._source = source

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            return self._prefix.read() + self._source.read()
        first = self._prefix.read(size)
        if len(first) == size:
            return first
        return first + self._source.read(size - len(first))


_XML_STREAM_CHUNK = 64 * 1024
_XML_STREAM_TAIL = 128
_INVALID_XML10_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_NUMERIC_CHARACTER_REFERENCE = re.compile(
    rb"&#(?:(?:[xX]([0-9A-Fa-f]+))|([0-9]+));"
)


def _is_valid_xml10_codepoint(value: int) -> bool:
    return (
        value in {0x09, 0x0A, 0x0D}
        or 0x20 <= value <= 0xD7FF
        or 0xE000 <= value <= 0xFFFD
        or 0x10000 <= value <= 0x10FFFF
    )


class _Xml10SanitizingReader:
    """Streaming XML 1.0 repair for dirty official registry exports.

    Some EDR rows contain numeric references to XML-forbidden control
    characters (for example ``&#11;``). ElementTree correctly rejects those
    references and would otherwise abort the entire multi-million-row import.

    The repair is intentionally narrow: only XML 1.0-invalid numeric character
    references and literal ASCII control bytes are replaced with one space.
    Structural XML errors are still allowed to fail the sync.
    """

    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self._pending = b""
        self._output = bytearray()
        self._eof = False
        self.invalid_reference_count = 0
        self.invalid_control_byte_count = 0

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunks: list[bytes] = []
            while True:
                chunk = self.read(_XML_STREAM_CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        if size == 0:
            return b""

        while len(self._output) < size and not self._eof:
            requested = max(_XML_STREAM_CHUNK, size)
            incoming = self._source.read(requested)
            if incoming:
                data = self._pending + incoming
                if len(data) <= _XML_STREAM_TAIL:
                    self._pending = data
                    continue
                process = data[:-_XML_STREAM_TAIL]
                self._pending = data[-_XML_STREAM_TAIL:]
                self._output.extend(self._sanitize(process))
                continue

            self._eof = True
            if self._pending:
                self._output.extend(self._sanitize(self._pending))
                self._pending = b""

        result = bytes(self._output[:size])
        del self._output[:size]
        return result

    def _sanitize(self, data: bytes) -> bytes:
        if not data:
            return data

        def replace_reference(match: re.Match[bytes]) -> bytes:
            try:
                if match.group(1) is not None:
                    value = int(match.group(1), 16)
                else:
                    value = int(match.group(2), 10)
            except (TypeError, ValueError):
                return match.group(0)

            if _is_valid_xml10_codepoint(value):
                return match.group(0)

            self.invalid_reference_count += 1
            return b" "

        repaired = _NUMERIC_CHARACTER_REFERENCE.sub(replace_reference, data)

        def replace_control(_match: re.Match[bytes]) -> bytes:
            self.invalid_control_byte_count += 1
            return b" "

        return _INVALID_XML10_CONTROL_BYTES.sub(replace_control, repaired)


@dataclass(slots=True)
class UaEdrParsedSubject:
    subject_kind: str
    record_id: str
    name: str
    name_normalized: str
    short_name: str | None = None
    registration_id: str | None = None
    legal_form: str | None = None
    status: str | None = None
    registration_info: str | None = None
    termination_info: str | None = None
    estate_manager: str | None = None
    family_farm: bool | None = None
    metadata: dict = field(default_factory=dict)

    def to_row(
        self,
        *,
        generation: str,
        source_resource_id: str | None,
        source_modified_at: str | None,
    ) -> dict:
        return {
            "generation": generation,
            "subject_kind": self.subject_kind,
            "record_id": self.record_id,
            "name": self.name[:1024],
            "name_normalized": self.name_normalized[:1024],
            "short_name": (self.short_name or "")[:1024] or None,
            "registration_id": (self.registration_id or "")[:64] or None,
            "legal_form": (self.legal_form or "")[:512] or None,
            "status": (self.status or "")[:512] or None,
            "registration_info": self.registration_info,
            "termination_info": self.termination_info,
            "estate_manager": self.estate_manager,
            "family_farm": self.family_farm,
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False, sort_keys=True),
            "source_resource_id": source_resource_id,
            "source_modified_at": source_modified_at,
            "raw_reference": f"ua-edr:{self.subject_kind}:{self.record_id}"[:512],
        }


class UaEdrXmlParser:
    """Parse SUBJECT/RECORD records without loading a multi-GB XML file in RAM."""

    def iter_subjects(self, stream: BinaryIO, *, subject_kind: str) -> Iterator[UaEdrParsedSubject]:
        if subject_kind not in {"company", "sole_trader"}:
            raise ValueError("subject_kind must be company or sole_trader")

        prefix = stream.read(_MAX_SECURITY_PREFIX)
        upper = prefix.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise ValueError("Unsafe XML declaration in EDR source.")

        prefixed_reader = _PrefixedReader(prefix, stream)
        reader = _Xml10SanitizingReader(prefixed_reader)
        self.last_invalid_reference_count = 0
        self.last_invalid_control_byte_count = 0
        root = None
        try:
            iterator = ET.iterparse(reader, events=("start", "end"))
            for event, element in iterator:
                if root is None and event == "start":
                    root = element
                    continue
                if event != "end":
                    continue

                tag = _local_name(element.tag)
                is_subject = tag == "SUBJECT"
                is_legacy_record = (
                    tag == "RECORD"
                    and any(_local_name(child.tag) in {"NAME", "FIO"} for child in list(element))
                )
                if not (is_subject or is_legacy_record):
                    # Do not clear child elements here: SUBJECT parsing needs their
                    # text when the parent closes. The whole subtree is cleared at
                    # the record boundary.
                    continue

                parsed = self._parse_subject(element, subject_kind=subject_kind)
                element.clear()
                # ElementTree otherwise leaves millions of cleared SUBJECT objects
                # referenced by the root. Clearing the root after each completed
                # top-level record keeps memory bounded for multi-GB exports.
                if root is not None and root is not element:
                    root.clear()
                if parsed is not None:
                    yield parsed
        finally:
            self.last_invalid_reference_count = reader.invalid_reference_count
            self.last_invalid_control_byte_count = reader.invalid_control_byte_count

    def _parse_subject(self, element: ET.Element, *, subject_kind: str) -> UaEdrParsedSubject | None:
        direct: dict[str, str] = {}
        metadata: dict[str, str] = {}

        for child in list(element):
            key = _local_name(child.tag)
            text = _bounded_text(child)
            if text:
                direct.setdefault(key, text)
                if key in _RELATION_TAGS:
                    metadata[key.casefold()] = text

        # Some historic exports represented records directly as <RECORD> with
        # fields as children, while current exports use <SUBJECT>. Both are read.
        name = (direct.get("NAME") or direct.get("FIO") or "").strip()
        if not name:
            return None

        record_id = (
            direct.get("RECORD")
            or element.attrib.get("record")
            or element.attrib.get("RECORD")
            or element.attrib.get("id")
            or element.attrib.get("ID")
            or ""
        ).strip()
        registration_id = (direct.get("EDRPOU") or "").strip() or None
        registration_info = direct.get("REGISTRATION")
        if not record_id:
            stable = "|".join(
                [subject_kind, name, registration_id or "", registration_info or ""]
            )
            record_id = "synthetic-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:32]
            metadata["synthetic_record_id"] = "true"

        farmer_raw = direct.get("FARMER") or direct.get("FAMILY_FARM")
        family_farm = None
        if farmer_raw:
            normalized_farmer = farmer_raw.strip().casefold()
            family_farm = normalized_farmer in {"1", "true", "yes", "так", "y"}
            metadata["farmer_raw"] = farmer_raw[:1024]

        # Preserve selected official fields which are useful later for profile/
        # relationship modelling without treating them as identity assertions.
        for key in (
            "BOSS",
            "FOUNDING_DOCUMENT_NUM",
            "EXECUTIVE_POWER",
            "REGISTRATION",
            "TERMINATED_INFO",
            "ESTATE_MANAGER",
        ):
            if direct.get(key):
                metadata.setdefault(key.casefold(), direct[key][:_MAX_TEXT_FIELD])

        return UaEdrParsedSubject(
            subject_kind=subject_kind,
            record_id=record_id[:255],
            name=name,
            name_normalized=normalize_ua_edr_name(name),
            short_name=direct.get("SHORT_NAME"),
            registration_id=registration_id if subject_kind == "company" else None,
            legal_form=direct.get("OPF") if subject_kind == "company" else None,
            status=direct.get("STAN"),
            registration_info=registration_info,
            termination_info=direct.get("TERMINATED_INFO"),
            estate_manager=direct.get("ESTATE_MANAGER"),
            family_farm=family_farm if subject_kind == "sole_trader" else None,
            metadata=metadata,
        )
