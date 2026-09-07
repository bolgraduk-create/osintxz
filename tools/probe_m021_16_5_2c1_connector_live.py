from __future__ import annotations

import traceback

from app.osint.connectors.user_scanner_connector import (
    UserScannerConnector,
)
from app.osint.models import (
    ConnectorRequest,
    OsintTarget,
    OsintTargetType,
)


print("=" * 88)
print("M021.16.5.2C1 USER SCANNER CONNECTOR DIAGNOSTIC")
print("=" * 88)

connector = UserScannerConnector()

print("executable:", connector.executable())
print("available:", connector.is_available())

request = ConnectorRequest(
    target=OsintTarget(
        target_type=OsintTargetType.EMAIL,
        value="bolgraduk@gmail.com",
    ),
    timeout=120,
    use_cache=False,
    save_raw_output=False,
    include_metadata=True,
    include_related=True,
)

print()
print("=== EXECUTE ===")

try:
    result = connector.execute(request)

    print("status:", result.status)
    print("error:", result.error)
    print("findings:", result.total_findings)
    print("metadata:", result.metadata)

    print()
    print("=== FINDINGS ===")

    for index, finding in enumerate(
        result.findings,
        start=1,
    ):
        print()
        print(f"#{index}")
        print("category:", finding.category)
        print("value:", finding.value)
        print("url:", finding.url)
        print("confidence:", finding.confidence)
        print("metadata:", finding.metadata)

except Exception as exc:
    print()
    print("[CONNECTOR CRASH]")
    print("type:", type(exc).__name__)
    print("repr:", repr(exc))
    print("str:", str(exc))

    print()
    traceback.print_exc()


print()
print("DIAGNOSTIC COMPLETE")
