from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)
from app.intelligence_sources.adapters.free_public_common import (
    PublicJsonClient,
    failure_result,
    first_text,
)


def _quoted(value: str) -> str:
    return '"' + value.replace("\\", " ").replace('"', " ").strip() + '"'


class OpenFdaAdapter(RemoteSourceAdapter):
    """Bounded search across several public openFDA datasets."""

    BASE = "https://api.fda.gov"

    def __init__(self, *, api_key: str | None = None, transport=None) -> None:
        self.api_key = (api_key or "").strip() or None
        self.client = PublicJsonClient(
            transport=transport,
            user_agent="OSINTXZ/1.0 openFDA",
        )

    @property
    def source_code(self) -> str:
        return "openfda"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({
            "manufacturer",
            "organization",
            "product",
            "drug",
            "device",
            "enforcement",
        })

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        specs = self._specs(query)
        records: list[RemoteSourceRecord] = []
        errors: list[str] = []
        retryable_failure = False

        for endpoint, search, kind in specs:
            params: dict[str, Any] = {
                "search": search,
                "limit": min(query.limit, 100),
            }
            if self.api_key:
                params["api_key"] = self.api_key
            try:
                payload = self.client.request_json(
                    "GET",
                    f"{self.BASE}{endpoint}",
                    params=params,
                    timeout=query.timeout,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    continue
                errors.append(f"{kind}: HTTP {exc.response.status_code}")
                retryable_failure = retryable_failure or (
                    exc.response.status_code == 429
                    or exc.response.status_code >= 500
                )
                continue
            except Exception as exc:
                errors.append(f"{kind}: {exc}")
                continue

            rows = payload.get("results", []) if isinstance(payload, dict) else []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                records.append(self._record(kind, row))
                if len(records) >= query.limit:
                    break
            if len(records) >= query.limit:
                break

        status = RemoteAdapterStatus.SUCCESS
        if errors and records:
            status = RemoteAdapterStatus.PARTIAL
        elif errors and not records:
            status = (
                RemoteAdapterStatus.PARTIAL
                if retryable_failure
                else RemoteAdapterStatus.FAILED
            )

        return RemoteAdapterResult(
            source=self.source_code,
            status=status,
            records=records[: query.limit],
            error="; ".join(errors) if errors else None,
            metadata={
                "records_found": len(records[: query.limit]),
                "datasets_queried": [kind for _, _, kind in specs],
                "api_key_optional": True,
                "raw_medical_event_data_not_requested": True,
            },
        )

    def _specs(self, query: RemoteSourceQuery):
        value = _quoted(query.value)
        c = query.capability
        if c in {"manufacturer", "organization"}:
            return [
                ("/drug/label.json", f"openfda.manufacturer_name:{value}", "drug_label"),
                ("/device/udi.json", f"company_name:{value}", "device_udi"),
            ]
        if c in {"product", "drug"}:
            return [
                ("/drug/label.json", f"openfda.brand_name:{value}", "drug_label"),
                ("/drug/label.json", f"openfda.generic_name:{value}", "drug_label"),
            ]
        if c == "device":
            return [
                ("/device/udi.json", f"brand_name:{value}", "device_udi"),
                ("/device/udi.json", f"device_description:{value}", "device_udi"),
            ]
        return [
            ("/drug/enforcement.json", f"recalling_firm:{value}", "drug_enforcement"),
        ]

    def _record(self, kind: str, row: dict[str, Any]) -> RemoteSourceRecord:
        if kind == "drug_label":
            openfda = row.get("openfda") if isinstance(row.get("openfda"), dict) else {}
            display = (
                first_text(openfda.get("brand_name"))
                or first_text(openfda.get("generic_name"))
                or first_text(openfda.get("manufacturer_name"))
                or "openFDA drug label"
            )
            rid = str(row.get("id") or row.get("set_id") or "").strip()
            identifiers = {
                k: v for k, v in {
                    "SET_ID": first_text(openfda.get("spl_set_id")) or rid or None,
                    "NDC": first_text(openfda.get("product_ndc")),
                }.items() if v
            }
            attrs = {
                "dataset": kind,
                "manufacturer_names": openfda.get("manufacturer_name") or [],
                "brand_names": openfda.get("brand_name") or [],
                "generic_names": openfda.get("generic_name") or [],
                "product_ndc": openfda.get("product_ndc") or [],
                "route": openfda.get("route") or [],
                "substance_name": openfda.get("substance_name") or [],
                "public_data": True,
            }
        elif kind == "device_udi":
            display = str(
                row.get("brand_name")
                or row.get("device_description")
                or row.get("company_name")
                or "openFDA device"
            ).strip()
            rid = str(
                row.get("public_device_record_key")
                or row.get("primary_di_number")
                or ""
            ).strip()
            identifiers = {
                k: str(v).strip()
                for k, v in {
                    "PRIMARY_DI": row.get("primary_di_number"),
                    "FEI": row.get("fei_number"),
                }.items()
                if str(v or "").strip()
            }
            attrs = {
                "dataset": kind,
                "company_name": row.get("company_name"),
                "brand_name": row.get("brand_name"),
                "device_description": row.get("device_description"),
                "version_model_number": row.get("version_model_number"),
                "publish_date": row.get("publish_date"),
                "public_data": True,
            }
        else:
            display = str(
                row.get("recalling_firm")
                or row.get("product_description")
                or "openFDA enforcement"
            ).strip()
            rid = str(
                row.get("recall_number")
                or row.get("event_id")
                or ""
            ).strip()
            identifiers = {
                k: str(v).strip()
                for k, v in {
                    "RECALL_NUMBER": row.get("recall_number"),
                    "EVENT_ID": row.get("event_id"),
                }.items()
                if str(v or "").strip()
            }
            attrs = {
                "dataset": kind,
                "recalling_firm": row.get("recalling_firm"),
                "product_description": row.get("product_description"),
                "reason_for_recall": row.get("reason_for_recall"),
                "status": row.get("status"),
                "classification": row.get("classification"),
                "recall_initiation_date": row.get("recall_initiation_date"),
                "public_data": True,
            }

        if not rid:
            rid = hashlib.sha256(
                json.dumps(
                    [kind, display, identifiers, attrs],
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest()

        return RemoteSourceRecord(
            source=self.source_code,
            record_id=rid,
            record_type=kind,
            display_name=display,
            source_url="https://open.fda.gov/data/",
            identifiers=identifiers,
            attributes=attrs,
        )
