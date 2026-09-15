import argparse
from app.application.registry_intelligence_service import RegistryIntelligenceService
from app.infrastructure.registries.gleif_client import GleifRegistryHttpClient
from app.registry_intelligence.contracts import RegistryDomain, RegistryQuery, RegistryQueryKind
from app.registry_intelligence.providers.gleif import GleifRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("value")
    parser.add_argument("--kind", choices=["name", "lei", "registration_id"], default="name")
    parser.add_argument("--country")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    kinds = {"name": RegistryQueryKind.NAME, "lei": RegistryQueryKind.LEI, "registration_id": RegistryQueryKind.REGISTRATION_ID}
    registry = RegistryProviderRegistry()
    registry.register(GleifRegistryProvider(client=GleifRegistryHttpClient()))
    service = RegistryIntelligenceService(registry)
    query = RegistryQuery(domain=RegistryDomain.BUSINESS, kind=kinds[args.kind], value=args.value, country=args.country, limit=args.limit, timeout=30)
    result = service.search(query)
    print("=" * 84)
    print("M022 GLEIF LIVE REGISTRY PROBE")
    print("=" * 84)
    print("query:", query.value)
    print("kind:", query.kind.value)
    print("country:", query.country)
    print("providers:", len(result.provider_results))
    print("records:", len(result.records))
    for pr in result.provider_results:
        print("\n---", pr.provider, "---")
        print("status:", pr.status)
        print("error:", pr.error)
        print("records:", len(pr.records))
        print("metadata:", pr.metadata)
    for i, rec in enumerate(result.records, 1):
        print(f"\n[{i}] {rec.display_name}")
        print("LEI:", rec.lei)
        print("country:", rec.country)
        print("jurisdiction:", rec.jurisdiction)
        print("status:", rec.status)
        print("registration_id:", rec.registration_id)
        print("legal_form:", rec.legal_form)
        print("legal_address:", rec.legal_address)
        print("headquarters_address:", rec.headquarters_address)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
