from __future__ import annotations

import sys
from app.osint.manager import OsintManager
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType
from app.osint.pipeline import OsintPipeline


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/probe_m021_16_7_2_phone_live.py +380XXXXXXXXX")
        return 2
    target_value = sys.argv[1].strip()
    manager = OsintManager()
    pipeline = OsintPipeline(manager)
    request = ConnectorRequest(
        target=OsintTarget(target_type=OsintTargetType.PHONE, value=target_value),
        timeout=120,
        use_cache=False,
        save_raw_output=False,
        include_metadata=True,
        include_related=True,
    )
    for name in ("LocalPhone", "PhoneInfoga"):
        result = pipeline.run_connector(name, request)
        print("\n---", name, "---")
        if result is None:
            print("NOT REGISTERED")
            continue
        print("status:", result.status)
        print("error:", result.error)
        print("findings:", result.total_findings)
        print("metadata:", result.metadata)
        for finding in result.findings:
            print(" ", finding.category, "|", finding.value, "|", finding.confidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
