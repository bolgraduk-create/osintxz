from __future__ import annotations

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.phone_intelligence import PhoneIntelligenceService
from app.osint.result import OsintFinding, OsintResult, ResultStatus


class LocalPhoneConnector(BaseConnector):
    """Local phone metadata provider backed by python-phonenumbers."""

    def __init__(self, *, default_region: str | None = None) -> None:
        self.service = PhoneIntelligenceService()
        self.default_region = default_region

    @property
    def name(self) -> str:
        return "LocalPhone"

    @property
    def description(self) -> str:
        return "Local phone validation, metadata and exact-search variant generation."

    @property
    def supported_targets(self) -> set[OsintTargetType]:
        return {OsintTargetType.PHONE}

    def is_available(self) -> bool:
        return self.service.available()

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(connector=self.name, status=ResultStatus.NOT_SUPPORTED, error="Unsupported target.")

        if not self.is_available():
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="Python package 'phonenumbers' is not installed.",
            )

        try:
            intelligence = self.service.analyze(request.target.value, default_region=self.default_region)
        except Exception as exc:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
                metadata={"local_only": True, "network_used": False},
            )

        result = OsintResult(connector=self.name, status=ResultStatus.SUCCESS)
        metadata = intelligence.metadata()

        result.add_finding(
            OsintFinding(
                category="phone_metadata",
                value=intelligence.e164 or request.target.value,
                source="LocalPhone/phonenumbers",
                confidence=0.95 if intelligence.valid else 0.70,
                reliability=0.95,
                metadata=metadata,
            )
        )

        if intelligence.valid and intelligence.e164:
            result.add_finding(
                OsintFinding(
                    category="phone",
                    value=intelligence.e164,
                    source="LocalPhone/phonenumbers",
                    confidence=0.97,
                    reliability=0.98,
                    metadata={
                        "canonical": True,
                        "validation_source": "python-phonenumbers",
                        "network_used": False,
                    },
                )
            )

        result.metadata = {
            "records_found": result.total_findings,
            "valid": intelligence.valid,
            "possible": intelligence.possible,
            "e164": intelligence.e164,
            "region_code": intelligence.region_code,
            "number_type": intelligence.number_type,
            "search_variants": list(intelligence.search_variants),
            "local_only": True,
            "network_used": False,
            "normalization_status": intelligence.normalization_status,
            "possible_e164_candidates": list(intelligence.possible_e164_candidates),
        }
        if intelligence.normalization_status == "ambiguous":
            result.status = ResultStatus.PARTIAL
            result.error = "Country context is required for unambiguous phone normalization."
        return result
