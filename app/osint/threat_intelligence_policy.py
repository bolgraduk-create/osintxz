"""Pure policy constants for automatic credentialed threat intelligence."""

from __future__ import annotations


AUTO_CREDENTIALED_THREAT_CONNECTORS: dict[str, str] = {
    "abuseipdb_connector": "abuseipdb_api_key",
    "alienvault_otx_connector": "otx_api_key",
    "urlscan_connector": "urlscan_api_key",
    "virustotal_connector": "virustotal_api_key",
}

AUTO_CREDENTIALED_THREAT_MODULES = frozenset(
    AUTO_CREDENTIALED_THREAT_CONNECTORS
)
