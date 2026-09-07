from app.registry_intelligence.contracts import RegistryDomain, RegistryQuery, RegistryQueryKind, RegistryResultStatus
from app.registry_intelligence.providers.gleif import GleifRegistryProvider

class FakeClient:
    def search_records(self, value, *, country=None, limit=20, timeout=30):
        return {"data": [self.row()]}
    def get_record(self, lei, *, timeout=30):
        return {"data": self.row(lei)}
    def row(self, lei="506700GE1G29325QX363"):
        return {"id": lei, "attributes": {"lei": lei, "entity": {"legalName": {"name": "GLOBAL LEGAL ENTITY IDENTIFIER FOUNDATION"}, "status": "ACTIVE", "jurisdiction": "CH", "legalAddress": {"addressLines": ["St. Alban-Vorstadt 5"], "city": "Basel", "postalCode": "4052", "country": "CH"}, "registeredAs": "CHE-200.595.965", "legalForm": {"id": "P2UQ"}}, "registration": {"status": "ISSUED", "corroborationLevel": "FULLY_CORROBORATED"}}}

def test_gleif_name_search_maps_record():
    provider = GleifRegistryProvider(client=FakeClient())
    result = provider.search(RegistryQuery(domain=RegistryDomain.BUSINESS, kind=RegistryQueryKind.NAME, value="GLEIF"))
    assert result.status is RegistryResultStatus.SUCCESS
    assert result.records[0].country == "CH"

def test_global_provider_accepts_country_filter():
    provider = GleifRegistryProvider(client=FakeClient())
    assert provider.supports(RegistryQuery(domain=RegistryDomain.BUSINESS, kind=RegistryQueryKind.NAME, value="X", country="UA"))

def test_bad_country_rejected():
    try:
        RegistryQuery(domain=RegistryDomain.BUSINESS, kind=RegistryQueryKind.NAME, value="X", country="UKR")
    except ValueError:
        return
    raise AssertionError("bad country accepted")
