from __future__ import annotations

import ipaddress
import json
import re
from urllib.parse import quote

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import failure_result, text_list


_ASN_RE = re.compile(r"^(?:AS)?(\d{1,10})$", re.I)


def _domain(value: str) -> str | None:
    raw = (value or "").strip().rstrip(".").casefold()
    if not raw or "://" in raw or any(ch.isspace() for ch in raw):
        return None
    try:
        ascii_name = raw.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if len(ascii_name) > 253 or "." not in ascii_name:
        return None
    labels = ascii_name.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return None
    return ascii_name


def _asn(value: str) -> int | None:
    match = _ASN_RE.fullmatch((value or "").strip())
    if not match:
        return None
    number = int(match.group(1))
    if not 1 <= number <= 4_294_967_295:
        return None
    return number


def _entity_summary(value) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, object]] = []
    for row in value[:20]:
        if not isinstance(row, dict):
            continue
        name = None
        card = row.get("vcardArray")
        if isinstance(card, list) and len(card) == 2 and isinstance(card[1], list):
            for item in card[1]:
                if (
                    isinstance(item, list)
                    and len(item) >= 4
                    and str(item[0]).casefold() == "fn"
                ):
                    name = str(item[3] or "").strip() or None
                    break
        out.append(
            {
                "handle": row.get("handle"),
                "roles": text_list(row.get("roles"), limit=10),
                "name": name,
            }
        )
    return out


class RdapBootstrapAdapter(RemoteSourceAdapter):
    API = "https://rdap.org"

    def __init__(self, *, transport=None) -> None:
        self.transport = transport

    @property
    def source_code(self) -> str:
        return "rdap_bootstrap"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset(
            {
                "domain",
                "domain_rdap",
                "ip",
                "ip_address",
                "ip_rdap",
                "asn",
                "autonomous_system",
                "asn_rdap",
            }
        )

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        capability = query.capability
        if capability in {"domain", "domain_rdap"}:
            value = _domain(query.value)
            kind = "domain"
            if value is None:
                return self._unsupported("Malformed domain name.")
        elif capability in {"ip", "ip_address", "ip_rdap"}:
            try:
                value = str(ipaddress.ip_address(query.value.strip()))
            except ValueError:
                return self._unsupported("Malformed IP address.")
            kind = "ip"
        elif capability in {"asn", "autonomous_system", "asn_rdap"}:
            number = _asn(query.value)
            if number is None:
                return self._unsupported("Malformed autonomous-system number.")
            value = str(number)
            kind = "autnum"
        else:
            return self._unsupported("Unsupported RDAP capability.")

        url = f"{self.API}/{kind}/{quote(value, safe='') if kind != 'domain' else quote(value, safe='.-')}"
        try:
            with httpx.Client(
                timeout=httpx.Timeout(float(query.timeout)),
                transport=self.transport,
                follow_redirects=True,
                headers={
                    "User-Agent": "OSINTXZ/1.0 RDAP",
                    "Accept": "application/rdap+json, application/json",
                },
            ) as client:
                response = client.get(url)
                if response.status_code == 404:
                    return RemoteAdapterResult(
                        source=self.source_code,
                        status=RemoteAdapterStatus.SUCCESS,
                        records=[],
                        metadata={"records_found": 0, "no_local_cache": True},
                    )
                if len(response.content) > 2_000_000:
                    raise ValueError("RDAP response exceeds download limit.")
                response.raise_for_status()
                payload = json.loads(response.content)

            if not isinstance(payload, dict):
                raise ValueError("RDAP response must be an object.")

            record_id = str(
                payload.get("handle")
                or payload.get("ldhName")
                or payload.get("name")
                or value
            ).strip()
            display_name = str(
                payload.get("ldhName")
                or payload.get("unicodeName")
                or payload.get("name")
                or payload.get("handle")
                or value
            ).strip()
            identifiers: dict[str, str] = {}
            if kind == "domain":
                identifiers["DOMAIN"] = str(payload.get("ldhName") or value)
            elif kind == "ip":
                identifiers["IP"] = value
                if payload.get("handle"):
                    identifiers["RDAP_HANDLE"] = str(payload["handle"])
            else:
                identifiers["ASN"] = f"AS{value}"

            record = RemoteSourceRecord(
                source=self.source_code,
                record_id=record_id or value,
                record_type=f"rdap_{kind}",
                display_name=display_name or value,
                source_url=url,
                identifiers=identifiers,
                attributes={
                    "object_class": payload.get("objectClassName"),
                    "status": text_list(payload.get("status"), limit=20),
                    "country": payload.get("country"),
                    "start_address": payload.get("startAddress"),
                    "end_address": payload.get("endAddress"),
                    "ip_version": payload.get("ipVersion"),
                    "start_autnum": payload.get("startAutnum"),
                    "end_autnum": payload.get("endAutnum"),
                    "entities": _entity_summary(payload.get("entities")),
                    "events": [
                        {
                            "action": event.get("eventAction"),
                            "date": event.get("eventDate"),
                        }
                        for event in (payload.get("events") or [])[:20]
                        if isinstance(event, dict)
                    ],
                    "exact_resource_lookup": True,
                    "public_registration_data": True,
                    "raw_response_stored": False,
                    "no_local_cache": True,
                },
            )
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.SUCCESS,
                records=[record],
                metadata={"records_found": 1, "no_local_cache": True},
            )
        except Exception as exc:
            return failure_result(self.source_code, exc)

    def _unsupported(self, message: str) -> RemoteAdapterResult:
        return RemoteAdapterResult(
            source=self.source_code,
            status=RemoteAdapterStatus.NOT_SUPPORTED,
            error=message,
        )
