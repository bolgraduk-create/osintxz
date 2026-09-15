"""Stable JSON transport contract for Registry Intelligence.

This module is deliberately framework-agnostic.  Desktop clients and the
central Registry Backend use the same serializer/deserializer so transport
never changes registry semantics, provenance, or identity confidence.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
    RegistrySourceType,
)


def registry_query_to_wire(query: RegistryQuery) -> dict[str, Any]:
    return {
        "domain": query.domain.value,
        "kind": query.kind.value,
        "value": query.value,
        "country": query.country,
        "limit": query.limit,
        "timeout": query.timeout,
        "sources": list(query.sources),
        "entity_kind": query.entity_kind.value if query.entity_kind else None,
    }


def registry_query_from_wire(payload: Mapping[str, Any]) -> RegistryQuery:
    entity_kind = payload.get("entity_kind")
    return RegistryQuery(
        domain=RegistryDomain(str(payload["domain"])),
        kind=RegistryQueryKind(str(payload["kind"])),
        value=str(payload["value"]),
        country=(str(payload["country"]) if payload.get("country") else None),
        limit=int(payload.get("limit", 20)),
        timeout=int(payload.get("timeout", 30)),
        sources=tuple(str(item) for item in (payload.get("sources") or ())),
        entity_kind=(RegistryEntityKind(str(entity_kind)) if entity_kind else None),
    )


def registry_record_to_wire(record: RegistryRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["domain"] = record.domain.value
    payload["entity_kind"] = record.entity_kind.value
    payload["source_type"] = record.source_type.value
    return payload


def registry_record_from_wire(payload: Mapping[str, Any]) -> RegistryRecord:
    return RegistryRecord(
        provider=str(payload["provider"]),
        domain=RegistryDomain(str(payload["domain"])),
        record_id=str(payload["record_id"]),
        display_name=str(payload["display_name"]),
        country=(str(payload["country"]) if payload.get("country") else None),
        jurisdiction=(str(payload["jurisdiction"]) if payload.get("jurisdiction") else None),
        status=(str(payload["status"]) if payload.get("status") is not None else None),
        registration_id=(
            str(payload["registration_id"])
            if payload.get("registration_id") is not None
            else None
        ),
        lei=(str(payload["lei"]) if payload.get("lei") is not None else None),
        legal_form=(
            str(payload["legal_form"]) if payload.get("legal_form") is not None else None
        ),
        legal_address=(
            str(payload["legal_address"])
            if payload.get("legal_address") is not None
            else None
        ),
        headquarters_address=(
            str(payload["headquarters_address"])
            if payload.get("headquarters_address") is not None
            else None
        ),
        source_url=(
            str(payload["source_url"]) if payload.get("source_url") is not None else None
        ),
        confidence=float(payload.get("confidence", 0.8)),
        reliability=float(payload.get("reliability", 0.8)),
        identifiers={
            str(key): str(value)
            for key, value in dict(payload.get("identifiers") or {}).items()
        },
        metadata=dict(payload.get("metadata") or {}),
        entity_kind=RegistryEntityKind(
            str(payload.get("entity_kind", RegistryEntityKind.LEGAL_ENTITY.value))
        ),
        source_type=RegistrySourceType(
            str(payload.get("source_type", RegistrySourceType.OFFICIAL_OPEN_DATA.value))
        ),
        trust_score=float(payload.get("trust_score", 0.8)),
        retrieved_at=(
            str(payload["retrieved_at"]) if payload.get("retrieved_at") is not None else None
        ),
        raw_reference=(
            str(payload["raw_reference"])
            if payload.get("raw_reference") is not None
            else None
        ),
        sensitive_legal_data=bool(payload.get("sensitive_legal_data", False)),
    )


def registry_provider_result_to_wire(result: RegistryProviderResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "status": result.status.value,
        "records": [registry_record_to_wire(record) for record in result.records],
        "error": result.error,
        "metadata": dict(result.metadata),
    }


def registry_provider_result_from_wire(
    payload: Mapping[str, Any],
) -> RegistryProviderResult:
    records_payload = payload.get("records") or []
    if not isinstance(records_payload, list):
        raise ValueError("Registry API records must be a list.")

    return RegistryProviderResult(
        provider=str(payload["provider"]).strip().casefold(),
        status=RegistryResultStatus(str(payload["status"])),
        records=[
            registry_record_from_wire(item)
            for item in records_payload
            if isinstance(item, Mapping)
        ],
        error=(str(payload["error"]) if payload.get("error") is not None else None),
        metadata=dict(payload.get("metadata") or {}),
    )
