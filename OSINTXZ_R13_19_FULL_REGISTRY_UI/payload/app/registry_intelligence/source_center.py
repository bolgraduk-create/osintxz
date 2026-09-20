from __future__ import annotations

from typing import Any


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", None) or value or "")


def _title(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().title()


def build_registry_center_snapshot(container: Any) -> dict[str, Any]:
    """Return a read-only UI snapshot of the live Registry provider registry.

    No provider search is executed here. Configuration state is derived only
    from the provider metadata already constructed by ServiceContainer.
    """

    registry = getattr(container, "registry_provider_registry", None)
    providers: list[dict[str, Any]] = []

    if registry is not None:
        for provider in tuple(registry.all()):
            info = getattr(provider, "info", None)
            if info is None:
                continue

            code = str(getattr(info, "name", "") or "").strip().casefold()
            if not code:
                continue

            domains = sorted(_enum_value(item) for item in getattr(info, "domains", ()) or ())
            query_kinds = sorted(
                _enum_value(item)
                for item in getattr(info, "query_kinds", ()) or ()
            )
            countries = sorted(str(item) for item in getattr(info, "countries", ()) or ())
            requires_credentials = bool(getattr(info, "requires_credentials", False))
            access_mode = _enum_value(getattr(info, "access_mode", None))
            sensitive = bool(getattr(info, "sensitive_legal_data", False))

            configured = not requires_credentials
            runnable_explicit = (
                configured
                and bool(getattr(info, "public_data_only", True))
                and access_mode in {"api", "public_automated"}
            )

            providers.append(
                {
                    "code": code,
                    "title": str(getattr(info, "display_name", "") or _title(code)),
                    "domains": domains,
                    "domainsText": ", ".join(_title(item) for item in domains),
                    "queryKinds": query_kinds,
                    "queryKindsText": ", ".join(_title(item) for item in query_kinds),
                    "countries": countries,
                    "countriesText": (
                        "GLOBAL"
                        if bool(getattr(info, "global_scope", False))
                        else ", ".join(countries)
                    ),
                    "globalScope": bool(getattr(info, "global_scope", False)),
                    "publicDataOnly": bool(getattr(info, "public_data_only", True)),
                    "requiresCredentials": requires_credentials,
                    "configured": configured,
                    "defaultEnabled": bool(getattr(info, "default_enabled", False)),
                    "automaticEligible": bool(getattr(info, "automatic_eligible", False)),
                    "runnableExplicit": runnable_explicit,
                    "priority": int(getattr(info, "priority", 100) or 100),
                    "accessMode": access_mode,
                    "sourceType": _enum_value(getattr(info, "source_type", None)),
                    "trustScore": float(getattr(info, "trust_score", 0.0) or 0.0),
                    "sensitiveLegalData": sensitive,
                    "runtimeStatus": (
                        "Ready"
                        if runnable_explicit
                        else "Needs credentials"
                        if requires_credentials
                        else "Manual / restricted"
                    ),
                }
            )

    providers.sort(key=lambda item: (int(item.get("priority") or 100), str(item.get("title") or "").casefold()))

    domain_codes = sorted({code for item in providers for code in item.get("domains", [])})
    query_kind_codes = sorted({code for item in providers for code in item.get("queryKinds", [])})
    country_codes = sorted({code for item in providers for code in item.get("countries", [])})

    return {
        "providers": providers,
        "providerCodes": [str(item["code"]) for item in providers],
        "providerLabels": [str(item["title"]) for item in providers],
        "domainCodes": domain_codes,
        "domainLabels": [_title(code) for code in domain_codes],
        "queryKindCodes": query_kind_codes,
        "queryKindLabels": [_title(code) for code in query_kind_codes],
        "countryCodes": country_codes,
        "counts": {
            "providers": len(providers),
            "ready": sum(1 for item in providers if item.get("configured")),
            "automatic": sum(1 for item in providers if item.get("automaticEligible")),
            "sensitive": sum(1 for item in providers if item.get("sensitiveLegalData")),
            "countries": len(country_codes),
            "domains": len(domain_codes),
            "queryKinds": len(query_kind_codes),
        },
    }
