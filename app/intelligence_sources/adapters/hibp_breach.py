from __future__ import annotations

from app.breach_intelligence.contracts import BreachResultStatus
from app.breach_intelligence.service import BreachIntelligenceService
from app.intelligence_sources.adapters.base import RemoteSourceAdapter
from app.intelligence_sources.adapters.contracts import (
    RemoteAdapterResult,
    RemoteAdapterStatus,
    RemoteSourceQuery,
    RemoteSourceRecord,
)


_STATUS_MAP = {
    BreachResultStatus.SUCCESS: RemoteAdapterStatus.SUCCESS,
    BreachResultStatus.PARTIAL: RemoteAdapterStatus.PARTIAL,
    BreachResultStatus.NOT_CONFIGURED: RemoteAdapterStatus.NOT_CONFIGURED,
    BreachResultStatus.NOT_SUPPORTED: RemoteAdapterStatus.NOT_SUPPORTED,
    BreachResultStatus.FAILED: RemoteAdapterStatus.FAILED,
}


class HibpBreachAdapter(RemoteSourceAdapter):
    def __init__(self, *, service: BreachIntelligenceService) -> None:
        self.service = service

    @property
    def source_code(self) -> str:
        return "hibp_breached_account"

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"email", "breach_lookup"})

    @property
    def configured(self) -> bool:
        return self.service.hibp_client.account_lookup_configured

    @property
    def automatic_enabled(self) -> bool:
        # Subscription-backed: ExposureFederationService selects it explicitly.
        return False

    def search(self, query: RemoteSourceQuery) -> RemoteAdapterResult:
        if not self.supports(query):
            return RemoteAdapterResult(
                source=self.source_code,
                status=RemoteAdapterStatus.NOT_SUPPORTED,
                error="Unsupported HIBP breach query.",
            )

        result = self.service.search_email(query.value, timeout=query.timeout)
        records = [self._to_record(item) for item in result.findings[: query.limit]]
        return RemoteAdapterResult(
            source=self.source_code,
            status=_STATUS_MAP[result.status],
            records=records,
            error=result.error,
            metadata={
                **result.metadata,
                "raw_secret_values_stored": False,
                "identity_confirmed": False,
            },
        )

    def _to_record(self, finding) -> RemoteSourceRecord:
        attrs = {
            "subject_type": finding.subject_type,
            "breach_name": finding.breach_name,
            "breach_title": finding.breach_title,
            "breach_domain": finding.breach_domain,
            "breach_date": finding.breach_date,
            "added_date": finding.added_date,
            "modified_date": finding.modified_date,
            "exposed_data_classes": list(finding.exposed_data_classes),
            "password_exposed": bool(finding.password_exposed),
            "occurrence_count": finding.occurrence_count,
            "subject_match_confirmed": True,
            "identity_confirmed": False,
            "raw_secret_values_stored": False,
            **finding.metadata,
        }
        return RemoteSourceRecord(
            source=self.source_code,
            record_id=finding.record_id,
            record_type="breach",
            display_name=(
                finding.breach_title
                or finding.breach_name
                or f"Breach {finding.record_id}"
            ),
            source_url=(
                f"https://haveibeenpwned.com/PwnedWebsites#{finding.breach_name}"
                if finding.breach_name
                else "https://haveibeenpwned.com/"
            ),
            identifiers={"BREACH_NAME": finding.breach_name}
            if finding.breach_name
            else {},
            attributes=attrs,
        )
