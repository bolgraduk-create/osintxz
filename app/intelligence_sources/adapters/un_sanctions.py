from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import failure_result, text_list


class UnSecurityCouncilSanctionsAdapter(RemoteSourceAdapter):
    XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    PAGE_URL = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
    MAX_BYTES = 4_000_000

    def __init__(self, *, transport=None) -> None:
        self.transport = transport

    @property
    def source_code(self) -> str:
        return "un_sc_sanctions"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"sanctions_name", "sanctions_entity", "un_sanctions"})

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        needle = " ".join(query.value.casefold().split())
        if len(needle) < 3:
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="UN sanctions search requires an explicit name with at least three characters.",
            )
        try:
            body = self._fetch(query.timeout)
            root = ET.fromstring(body)
            records: list[RemoteSourceRecord] = []
            for section, tag, kind in (
                ("INDIVIDUALS", "INDIVIDUAL", "individual"),
                ("ENTITIES", "ENTITY", "entity"),
            ):
                parent = root.find(section)
                if parent is None:
                    continue
                for row in parent.findall(tag):
                    name_parts = [
                        self._text(row, field)
                        for field in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME")
                    ]
                    primary = " ".join(part for part in name_parts if part).strip()
                    aliases = []
                    alias_tag = "INDIVIDUAL_ALIAS" if kind == "individual" else "ENTITY_ALIAS"
                    for alias in row.findall(alias_tag):
                        text = self._text(alias, "ALIAS_NAME")
                        if text:
                            aliases.append(text)
                    haystack = " ".join([primary, *aliases]).casefold()
                    if needle not in " ".join(haystack.split()):
                        continue
                    reference = self._text(row, "REFERENCE_NUMBER") or self._text(row, "DATAID") or primary
                    if not reference or not primary:
                        continue
                    records.append(RemoteSourceRecord(
                        source=self.source_code,
                        record_id=reference,
                        record_type=f"un_sanctions_{kind}",
                        display_name=primary,
                        source_url=self.PAGE_URL,
                        identifiers={"UN_REFERENCE_NUMBER": reference} if reference else {},
                        attributes={
                            "aliases": text_list(aliases, limit=30),
                            "listed_on": self._text(row, "LISTED_ON"),
                            "designation": self._designation_values(row),
                            "candidate_only": True,
                            "sanctions_listing_match_only": True,
                            "identity_confirmation_required": True,
                            "guilt_or_criminality_inference_prohibited": True,
                            "listing_is_not_proof_of_same_person_or_entity": True,
                            "raw_xml_stored": False,
                            "transient_feed_only": True,
                            "no_local_cache": True,
                        },
                    ))
                    if len(records) >= query.limit:
                        break
                if len(records) >= query.limit:
                    break
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=records,
                metadata={
                    "records_found": len(records),
                    "feed_persisted": False,
                    "transient_feed_bytes_only": True,
                    "explicit_search_only": True,
                },
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _fetch(self, timeout: int) -> bytes:
        headers = {"User-Agent": "OSINTXZ/1.0 UNSanctions", "Accept": "application/xml,text/xml"}
        with httpx.Client(timeout=httpx.Timeout(float(timeout)), transport=self.transport, follow_redirects=False, headers=headers) as client:
            response = client.get(self.XML_URL)
            if 300 <= response.status_code < 400:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("UN sanctions redirect is missing Location.")
                target = urljoin(self.XML_URL, location)
                host = (urlsplit(target).hostname or "").casefold()
                if host != "scsanctions.un.org" and not host.endswith(".blob.core.windows.net"):
                    raise ValueError("UN sanctions redirect target is not trusted.")
                response = client.get(target)
            if len(response.content) > self.MAX_BYTES:
                raise ValueError("UN sanctions XML exceeds download limit.")
            response.raise_for_status()
            return bytes(response.content)

    @staticmethod
    def _designation_values(node: ET.Element) -> list[str]:
        parent = node.find("DESIGNATION")
        if parent is None:
            return []
        return [
            (item.text or "").strip()
            for item in list(parent)[:20]
            if (item.text or "").strip()
        ]

    @staticmethod
    def _text(node: ET.Element, name: str) -> str | None:
        child = node.find(name)
        if child is None or child.text is None:
            return None
        text = child.text.strip()
        return text or None
