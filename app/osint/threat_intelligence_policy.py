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


# Conservative automatic-request caps for one traversal/search run. These are
# application safeguards, not claims about upstream provider account quotas.
AUTO_CREDENTIALED_THREAT_RUN_LIMITS: dict[str, int] = {
    "abuseipdb_connector": 4,
    "alienvault_otx_connector": 4,
    "urlscan_connector": 3,
    "virustotal_connector": 2,
}
