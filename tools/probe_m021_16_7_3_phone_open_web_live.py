from __future__ import annotations

import sys
from uuid import uuid4

import app.database.session as session_module
from app.core.service_container import ServiceContainer
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: probe_m021_16_7_3_phone_open_web_live.py +380XXXXXXXXX")
        return 2

    target = sys.argv[1].strip()
    session = session_module.create_session()

    try:
        container = ServiceContainer(session)
        query = OpenWebQuery(
            target_type=OsintTargetType.PHONE,
            value=target,
            case_id=str(uuid4()),
            limit=10,
            timeout=30,
            depth=0,
        )

        response = container.open_web_discovery_service.discover(query)

        print("=" * 76)
        print("PHONE EXACT OPEN-WEB LIVE PROBE")
        print("=" * 76)
        print("target:", target)
        print("providers:", response.provider_count)
        print("documents:", len(response.documents))

        for result in response.results:
            print("\n---", result.provider, "---")
            print("status:", result.status)
            print("error:", result.error)
            print("documents:", result.total_documents)
            print("metadata:", result.metadata)

        for document in response.documents:
            print("\nVERIFIED DOCUMENT")
            print("url:", document.url)
            print("title:", document.title)
            print("confidence:", document.confidence)
            print("metadata:", document.metadata)

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
