from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


print("=" * 80)
print("M021.16.3 LIVE WEB RUNTIME PROBE")
print("=" * 80)

container = ServiceContainer()

print("\n=== REGISTERED PROVIDERS ===")

for provider in container.open_web_provider_registry.all():
    info = provider.info
    print(
        f"name={info.name} "
        f"enabled={info.default_enabled} "
        f"eligible={info.automatic_eligible} "
        f"targets={[x.value for x in info.supported_targets]}"
    )

query = OpenWebQuery(
    target_type=OsintTargetType.URL,
    value="https://www.uic.edu/about/contact-us/",
    limit=25,
    timeout=30,
)

print("\n=== AUTOMATIC PROVIDERS FOR URL ===")

providers = container.open_web_provider_registry.automatic_for(query)

for provider in providers:
    print(" -", provider.info.name)

print("\n=== LIVE WEB DIRECT ===")

provider = getattr(
    container,
    "live_web_open_web_provider",
    None,
)

if provider is None:
    print("[FAIL] live_web_open_web_provider missing from ServiceContainer")
else:
    result = provider.search(query)

    print("provider:", result.provider)
    print("status:", result.status)
    print("error:", result.error)
    print("documents:", len(result.documents))
    print("metadata:", result.metadata)

    for index, document in enumerate(
        result.documents,
        start=1,
    ):
        print()
        print(f"DOCUMENT {index}")
        print("url:", document.url)
        print("title:", document.title)
        print("content_type:", document.content_type)
        print("text_length:", len(document.text or ""))
        print("text_preview:")
        print((document.text or "")[:1500])

print("\n=== DISCOVERY SERVICE ===")

discovery = container.open_web_discovery_service.discover(query)

print("provider results:", len(discovery.results))
print("combined documents:", len(discovery.documents))

for result in discovery.results:
    print()
    print("RESULT")
    print(" provider:", result.provider)
    print(" status:", result.status)
    print(" error:", result.error)
    print(" documents:", len(result.documents))
    print(" metadata:", result.metadata)

print("\nPROBE COMPLETE")
