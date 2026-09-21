"""Live, passive smoke-check for configured threat-intelligence APIs.

This script intentionally never prints credential values. It performs one
bounded read-only lookup per configured connector.
"""

from __future__ import annotations

import argparse

from app.osint.connectors.abuseipdb_connector import AbuseIPDBConnector
from app.osint.connectors.alienvault_otx_connector import AlienVaultOTXConnector
from app.osint.connectors.urlscan_connector import URLScanConnector
from app.osint.connectors.virustotal_connector import VirusTotalConnector
from app.osint.credential_policy import (
    configured_threat_intelligence_modules,
)
from app.osint.models import ConnectorRequest, OsintTarget, OsintTargetType


CHECKS = (
    (
        "AbuseIPDB",
        "abuseipdb_connector",
        AbuseIPDBConnector,
        OsintTargetType.IP,
        "8.8.8.8",
    ),
    (
        "AlienVault OTX",
        "alienvault_otx_connector",
        AlienVaultOTXConnector,
        OsintTargetType.DOMAIN,
        "example.com",
    ),
    (
        "urlscan.io",
        "urlscan_connector",
        URLScanConnector,
        OsintTargetType.DOMAIN,
        "example.com",
    ),
    (
        "VirusTotal",
        "virustotal_connector",
        VirusTotalConnector,
        OsintTargetType.DOMAIN,
        "example.com",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check configured passive threat-intelligence APIs."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Per-request timeout in seconds (default: 15).",
    )
    args = parser.parse_args()

    configured = configured_threat_intelligence_modules()
    print("Threat Intelligence API smoke-check")
    print("=" * 44)

    failures = 0
    for label, module, connector_cls, target_type, value in CHECKS:
        connector = connector_cls()
        is_configured = module in configured and connector.is_available()

        if not is_configured:
            print(f"{label:<18} NOT CONFIGURED")
            continue

        request = ConnectorRequest(
            target=OsintTarget(
                target_type=target_type,
                value=value,
            ),
            timeout=max(1, int(args.timeout)),
            use_cache=False,
            save_raw_output=False,
            include_metadata=True,
            include_related=False,
            limit=3,
        )

        try:
            result = connector.execute(request)
        except Exception as exc:
            failures += 1
            print(
                f"{label:<18} EXCEPTION"
                f" | {exc.__class__.__name__}: {exc}"
            )
            continue

        status = result.status.value.upper()
        findings = int(result.total_findings)
        error = str(result.error or "").strip()
        suffix = f" | {error}" if error else ""
        print(
            f"{label:<18} {status:<13}"
            f" | findings={findings}{suffix}"
        )

        if status in {"FAILED", "NOT_AVAILABLE"}:
            failures += 1

    print("=" * 44)
    print(
        "Configured modules:",
        len(configured),
        "| hard failures:",
        failures,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
