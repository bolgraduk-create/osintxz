from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence_sources.adapters.contracts import RemoteAdapterStatus


@dataclass(slots=True)
class ExposureSummary:
    total_records: int = 0
    breach_records: int = 0
    darkweb_records: int = 0
    indexed_leak_records: int = 0
    paste_records: int = 0
    stealer_log_records: int = 0
    secret_alert_records: int = 0
    verified_scope_records: int = 0
    password_exposed: bool = False
    secret_material_present: bool = False
    raw_secret_values_stored: bool = False
    provider_statuses: dict[str, RemoteAdapterStatus] = field(default_factory=dict)


@dataclass(slots=True)
class ExposureSearchResult:
    capability: str
    value: str
    federated_result: object
    summary: ExposureSummary
