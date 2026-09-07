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
print("M021.16.6.3.2 USER SCANNER USERNAME LIVE DIAGNOSTIC")
print("=" * 88)

connector = UserScannerConnector()

print("executable:", connector.executable())
print("available:", connector.is_available())
print(
    "supported:",
    [item.value for item in connector.supported_targets]
)

print()
print("=== COMMAND ===")

try:
    command = connector._build_command(
        executable=connector.executable() or "missing",
        target_type=OsintTargetType.USERNAME,
        value="wixxlexx",
        output=__import__("pathlib").Path(
            "storage/user_scanner_username_probe.json"
        ),
        timeout=60,
    )

    print(command)

except Exception:
    traceback.print_exc()


print()
print("=== CONNECTOR EXECUTE ===")

request = ConnectorRequest(
    target=OsintTarget(
        target_type=OsintTargetType.USERNAME,
        value="wixxlexx",
    ),
    timeout=120,
    use_cache=False,
    save_raw_output=False,
    include_metadata=True,
    include_related=True,
)

try:
    result = connector.execute(request)

    print("status:", result.status)
    print("error:", result.error)
    print("findings:", result.total_findings)
    print("metadata:", result.metadata)

    print()
    print("FIRST FINDINGS:")

    for finding in result.findings[:20]:
        print(
            finding.category,
            "|",
            finding.value,
            "|",
            finding.url,
        )

except Exception as exc:
    print("[CRASH]")
    print(type(exc).__name__)
    print(repr(exc))
    traceback.print_exc()


print()
print("DIAGNOSTIC COMPLETE")
