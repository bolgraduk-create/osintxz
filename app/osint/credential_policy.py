"""R13.28.1 credential-aware threat-intelligence activation policy."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, settings


AUTO_CREDENTIALED_THREAT_CONNECTORS: dict[str, str] = {
    "abuseipdb_connector": "abuseipdb_api_key",
    "alienvault_otx_connector": "otx_api_key",
    "urlscan_connector": "urlscan_api_key",
    "virustotal_connector": "virustotal_api_key",
}


def secret_text(value: Any) -> str:
    """Return a secret value as text without leaking it into metadata/logs."""
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "").strip()
    return str(value or "").strip()


def configured_threat_intelligence_modules(
    config: Settings = settings,
) -> frozenset[str]:
    """Return only explicitly supported passive credentialed TI connectors."""
    configured: set[str] = set()
    for module, setting_name in AUTO_CREDENTIALED_THREAT_CONNECTORS.items():
        if secret_text(getattr(config, setting_name, None)):
            configured.add(module)
    return frozenset(configured)


def connector_secret(
    setting_name: str,
    config: Settings = settings,
) -> str:
    return secret_text(getattr(config, setting_name, None))
