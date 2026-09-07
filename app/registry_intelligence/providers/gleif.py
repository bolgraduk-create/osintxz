import re
import httpx
from app.registry_intelligence.contracts import RegistryDomain, RegistryProviderInfo, RegistryProviderResult, RegistryQuery, RegistryQueryKind, RegistryRecord, RegistryResultStatus
from app.registry_intelligence.provider import RegistryProvider

class GleifRegistryProvider(RegistryProvider):
    _LEI_RE = re.compile(r"^[A-Z0-9]{20}$")

    def __init__(self, *, client) -> None:
        self.client = client
        self._info = RegistryProviderInfo(name="gleif", display_name="GLEIF Global LEI Index", domains=frozenset({RegistryDomain.BUSINESS}), query_kinds=frozenset({RegistryQueryKind.NAME, RegistryQueryKind.LEI, RegistryQueryKind.REGISTRATION_ID}), global_scope=True, public_data_only=True, requires_credentials=False, default_enabled=True, priority=10)

    @property
    def info(self) -> RegistryProviderInfo:
        return self._info

    def search(self, query: RegistryQuery) -> RegistryProviderResult:
        if not self.supports(query):
            return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.NOT_SUPPORTED, error="Unsupported GLEIF query.")
        if query.kind is RegistryQueryKind.LEI and not self._LEI_RE.fullmatch(query.value.strip().upper()):
            return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.NOT_SUPPORTED, error="Malformed LEI.")
        try:
            if query.kind is RegistryQueryKind.LEI or self._LEI_RE.fullmatch(query.value.strip().upper()):
                payload = self.client.get_record(query.value.strip().upper(), timeout=query.timeout)
            else:
                payload = self.client.search_records(query.value.strip(), country=query.country, limit=query.limit, timeout=query.timeout)
            data = payload.get("data", [])
            rows = [data] if isinstance(data, dict) else [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
            records = [r for row in rows if (r := self._to_record(row)) is not None]
            if query.kind is RegistryQueryKind.LEI:
                records = [r for r in records if (r.lei or "").upper() == query.value.strip().upper()]
            if query.kind is RegistryQueryKind.REGISTRATION_ID:
                # Fulltext is candidate discovery, not identifier verification.
                records = [r for r in records if (r.registration_id or "").strip().casefold() == query.value.strip().casefold()]
            if query.country:
                records = [r for r in records if (r.country or "").upper() == query.country.strip().upper()]
            return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.SUCCESS, records=records[: query.limit], metadata={"records_found": len(records), "public_data_only": True, "credentials_required": False, "global_scope": True})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.PARTIAL,
                    error="Public upstream rate limited (HTTP 429). Retry later.",
                    metadata={"rate_limited": True, "retryable": True})
            if exc.response.status_code == 404:
                return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.SUCCESS,
                    metadata={"records_found": 0})
            return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.FAILED,
                error=f"Public registry HTTP {exc.response.status_code}.", metadata={"failure_isolated": True})
        except Exception as exc:
            return RegistryProviderResult(provider="gleif", status=RegistryResultStatus.FAILED, error=str(exc), metadata={"failure_isolated": True})

    def _to_record(self, row):
        attributes = row.get("attributes")
        if not isinstance(attributes, dict):
            return None
        entity = attributes.get("entity") if isinstance(attributes.get("entity"), dict) else {}
        registration = attributes.get("registration") if isinstance(attributes.get("registration"), dict) else {}
        lei = str(attributes.get("lei") or row.get("id") or "").strip()
        legal_name = entity.get("legalName")
        name = str(legal_name.get("name") if isinstance(legal_name, dict) else legal_name or "").strip()
        if not lei or not name:
            return None
        legal_address = entity.get("legalAddress") if isinstance(entity.get("legalAddress"), dict) else {}
        headquarters = entity.get("headquartersAddress") if isinstance(entity.get("headquartersAddress"), dict) else {}
        registered_at = entity.get("registeredAt") if isinstance(entity.get("registeredAt"), dict) else {}
        # registeredAt.id identifies the registration authority, not the company.
        registration_id = str(entity.get("registeredAs") or "").strip() or None
        legal_form_data = entity.get("legalForm") if isinstance(entity.get("legalForm"), dict) else {}
        legal_form = str(legal_form_data.get("id") or legal_form_data.get("other") or "").strip() or None
        return RegistryRecord(provider="gleif", domain=RegistryDomain.BUSINESS, record_id=lei, display_name=name, country=str(legal_address.get("country") or "").strip().upper() or None, jurisdiction=str(entity.get("jurisdiction") or "").strip() or None, status=str(entity.get("status") or registration.get("status") or "").strip() or None, registration_id=registration_id, lei=lei, legal_form=legal_form, legal_address=self._addr(legal_address), headquarters_address=self._addr(headquarters), source_url=f"https://api.gleif.org/api/v1/lei-records/{lei}", confidence=0.96, reliability=0.97, identifiers={"LEI": lei, **({"REGISTRATION_ID": registration_id} if registration_id else {})}, metadata={"registration_status": registration.get("status"), "corroboration_level": registration.get("corroborationLevel")})

    @staticmethod
    def _addr(value) -> str | None:
        if not isinstance(value, dict):
            return None
        parts: list[str] = []
        lines = value.get("addressLines")
        if isinstance(lines, list):
            parts.extend(str(x).strip() for x in lines if str(x).strip())
        for key in ("city", "region", "postalCode", "country"):
            item = str(value.get(key) or "").strip()
            if item:
                parts.append(item)
        return ", ".join(parts) or None
