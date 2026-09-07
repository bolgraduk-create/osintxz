from __future__ import annotations

import importlib.util

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.live_web import (
    LiveWebOpenWebProvider,
)


print("=" * 80)
print("M021.16.3.1 LIVE WEB TLS RUNTIME PROBE")
print("=" * 80)

print(
    "truststore installed:",
    importlib.util.find_spec("truststore") is not None,
)

provider = LiveWebOpenWebProvider()

query = OpenWebQuery(
    target_type=OsintTargetType.URL,
    value="https://www.uic.edu/about/contact-us/",
    limit=25,
    timeout=30,
)

result = provider.search(query)

print("provider:", result.provider)
print("status:", result.status)
print("error:", result.error)
print("documents:", len(result.documents))

for document in result.documents:
    print("url:", document.url)
    print("title:", document.title)
    print("content_type:", document.content_type)
    print("text_length:", len(document.text or ""))
    print("preview:")
    print((document.text or "")[:1000])

print("\nPROBE COMPLETE")
