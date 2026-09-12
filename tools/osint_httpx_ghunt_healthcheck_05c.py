"""
OSINT Expansion 05C — production runtime post-fix health-check.

No OSINT queries are executed.

Checks:
- HTTPXConnector can resolve the managed ProjectDiscovery httpx binary.
- GHuntConnector passes its production UTF-8 CLI health-check.
"""

from __future__ import annotations

from app.osint.connectors.ghunt_connector import GHuntConnector
from app.osint.connectors.httpx_connector import HTTPXConnector


def main() -> int:
    print("OSINT Expansion 05C — Production Runtime Health")
    print("=" * 60)

    httpx = HTTPXConnector()
    ghunt = GHuntConnector()

    httpx_ready = httpx.is_available()
    ghunt_ready = ghunt.is_available()

    print(
        f"httpx  production_available={httpx_ready}"
    )
    print(
        f"ghunt  production_available={ghunt_ready}"
    )

    if not httpx_ready:
        print("")
        print("OSINT EXPANSION 05C HEALTH: FAIL")
        print("ProjectDiscovery httpx is not available.")
        return 1

    if not ghunt_ready:
        print("")
        print("OSINT EXPANSION 05C HEALTH: PARTIAL")
        print(
            "HTTPX is ready; GHunt remains unavailable after the UTF-8 "
            "production health-check."
        )
        return 0

    print("")
    print("OSINT EXPANSION 05C HEALTH: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
