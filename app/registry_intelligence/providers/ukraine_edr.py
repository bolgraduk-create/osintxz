"""Ukraine EDR provider backed by the locally synchronized official open-data mirror."""
from __future__ import annotations

import json

from app.infrastructure.registries.ukraine_edr_downloader import OFFICIAL_DATASET_PAGE
from app.registry_intelligence.contracts import (
    RegistryDomain,
    RegistryEntityKind,
    RegistryProviderResult,
    RegistryQuery,
    RegistryQueryKind,
    RegistryRecord,
    RegistryResultStatus,
)
from app.registry_intelligence.countries.ukraine import UA_EDR_PROVIDER_INFO
from app.registry_intelligence.provider import RegistryProvider
from app.repositories.registry_ua_edr_repository import UaEdrRepository


class UkraineEdrRegistryProvider(RegistryProvider):
    def __init__(self, *, repository: UaEdrRepository) -> None:
        self.repository = repository
        self._info = UA_EDR_PROVIDER_INFO

    @property
    def info(self):
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error="Unsupported Ukraine EDR query.",
            )

        generation = self.repository.active_generation()
        if not generation:
            return RegistryProviderResult(
                provider=self.info.name,
                status=RegistryResultStatus.NOT_SUPPORTED,
                error=(
                    "Registry Backend Ukraine EDR mirror is not synchronized. "
                    "Run the server-side EDR ingestion worker before serving queries."
                ),
                metadata={"cache_state": "missing", "action_required": "backend_sync"},
            )

        if query.kind is RegistryQueryKind.REGISTRATION_ID:
            rows = self.repository.search_registration_id(query.value, limit=query.limit)
            exact_identity = True
        else:
            requested_kind = None
            if query.entity_kind is RegistryEntityKind.COMPANY:
                requested_kind = "company"
            elif query.entity_kind in {RegistryEntityKind.SOLE_TRADER, RegistryEntityKind.PERSON}:
                requested_kind = "sole_trader"
            elif query.kind is RegistryQueryKind.PERSON_NAME:
                requested_kind = "sole_trader"
            rows = self.repository.search_name(
                query.value,
                subject_kind=requested_kind,
                limit=query.limit,
            )
            exact_identity = False

        records = [self._to_record(row, exact_identity=exact_identity) for row in rows]
        return RegistryProviderResult(
            provider=self.info.name,
            status=RegistryResultStatus.SUCCESS,
            records=records,
            metadata={
                "records_found": len(records),
                "country": "UA",
                "mirror_generation": generation,
                "public_data_only": True,
                "name_results_are_candidates": not exact_identity,
            },
        )

    def _to_record(self, row, *, exact_identity: bool) -> RegistryRecord:
        metadata = self._metadata(row.metadata_json)
        metadata.update(
            {
                "subject_kind": row.subject_kind,
                "short_name": row.short_name,
                "registration_info": row.registration_info,
                "termination_info": row.termination_info,
                "estate_manager": row.estate_manager,
                "family_farm": row.family_farm,
            }
        )
        if not exact_identity:
            metadata["candidate_only"] = True
            metadata["identity_uncertainty"] = "name_only_match"

        entity_kind = (
            RegistryEntityKind.COMPANY
            if row.subject_kind == "company"
            else RegistryEntityKind.SOLE_TRADER
        )
        registration_id = row.registration_id if row.subject_kind == "company" else None
        identifiers = {"EDRPOU": registration_id} if registration_id else {}
        return RegistryRecord(
            provider=self.info.name,
            domain=RegistryDomain.BUSINESS,
            record_id=f"{row.subject_kind}:{row.record_id}",
            display_name=row.name,
            country="UA",
            jurisdiction="UA",
            status=row.status,
            registration_id=registration_id,
            legal_form=row.legal_form,
            source_url=OFFICIAL_DATASET_PAGE,
            confidence=0.98 if exact_identity else (0.70 if row.subject_kind == "company" else 0.55),
            reliability=0.96,
            identifiers=identifiers,
            metadata=metadata,
            entity_kind=entity_kind,
            source_type=self.info.source_type,
            trust_score=0.96,
            raw_reference=f"ua-edr:{row.subject_kind}:{row.record_id}",
        )

    @staticmethod
    def _metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
