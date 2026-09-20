from __future__ import annotations

from typing import Any


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", None) or value or "")


def _call_bool(obj: Any, name: str, default: bool = False) -> bool:
    try:
        value = getattr(obj, name, default)
    except Exception:
        return False
    if callable(value):
        try:
            return bool(value())
        except Exception:
            return False
    try:
        return bool(value)
    except Exception:
        return bool(default)


def _title(value: str) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().title()


def _descriptor_row(descriptor: Any) -> dict[str, Any]:
    categories = sorted(_enum_value(item) for item in getattr(descriptor, "categories", ()) or ())
    capabilities = sorted(str(item) for item in getattr(descriptor, "capabilities", ()) or ())
    countries = sorted(str(item) for item in getattr(descriptor, "countries", ()) or ())
    access_mode = _enum_value(getattr(descriptor, "access_mode", None))
    return {
        "title": str(getattr(descriptor, "display_name", "") or ""),
        "capabilities": capabilities,
        "capabilitiesText": ", ".join(capabilities),
        "categories": categories,
        "categoryText": ", ".join(_title(item) for item in categories),
        "countries": countries,
        "countriesText": "GLOBAL" if bool(getattr(descriptor, "global_scope", False)) else ", ".join(countries),
        "accessMode": access_mode,
        "cost": _enum_value(getattr(descriptor, "cost", None)),
        "sensitivity": _enum_value(getattr(descriptor, "default_sensitivity", None)),
        "documentationUrl": str(getattr(descriptor, "documentation_url", "") or ""),
        "notes": str(getattr(descriptor, "notes", "") or ""),
        "requiresCredentials": bool(getattr(descriptor, "requires_credentials", False)),
        "requiresVerifiedScope": access_mode == "verified_scope",
    }


def build_source_center_snapshot(container: Any) -> dict[str, Any]:
    """Build a read-only UI snapshot of every known source execution layer.

    This function performs no remote I/O. Availability probes are limited to
    connector/adapter local configuration checks already exposed by the runtime.
    """

    rows: list[dict[str, Any]] = []
    seen_catalog_codes: set[str] = set()
    catalog = getattr(container, "intelligence_source_catalog", None)
    coverage = getattr(container, "remote_source_coverage", None)

    remote_registry = getattr(container, "remote_source_adapter_registry", None)
    if remote_registry is not None:
        for adapter in tuple(remote_registry.all()):
            code = str(getattr(adapter, "source_code", "") or "").strip().casefold()
            if not code:
                continue
            descriptor = catalog.get(code) if catalog is not None else None
            descriptor_data = _descriptor_row(descriptor) if descriptor is not None else {}
            configured = _call_bool(adapter, "configured", True)
            automatic = _call_bool(adapter, "automatic_enabled", False)
            entry = coverage.get(code) if coverage is not None else None
            status = _enum_value(getattr(entry, "status", None)) or "active"
            seen_catalog_codes.add(code)
            rows.append({
                "id": f"federation:{code}",
                "code": code,
                "title": descriptor_data.get("title") or _title(code),
                "subsystem": "Federation",
                "kind": "remote_adapter",
                "runtimeStatus": "Ready" if configured else "Needs configuration",
                "implementationStatus": status,
                "configured": configured,
                "automatic": automatic,
                "searchable": True,
                "routePage": "sources",
                "capabilities": sorted(str(item) for item in getattr(adapter, "capabilities", ()) or ()),
                "capabilitiesText": ", ".join(sorted(str(item) for item in getattr(adapter, "capabilities", ()) or ())),
                "countries": descriptor_data.get("countries", sorted(str(item) for item in getattr(adapter, "countries", ()) or ())),
                "countriesText": descriptor_data.get("countriesText") or ("GLOBAL" if bool(getattr(adapter, "global_scope", False)) else ", ".join(sorted(str(item) for item in getattr(adapter, "countries", ()) or ()))),
                "accessMode": descriptor_data.get("accessMode", "runtime"),
                "cost": descriptor_data.get("cost", "unknown"),
                "sensitivity": descriptor_data.get("sensitivity", "public"),
                "documentationUrl": descriptor_data.get("documentationUrl", ""),
                "notes": descriptor_data.get("notes", ""),
                "requiresCredentials": descriptor_data.get("requiresCredentials", not configured),
                "requiresVerifiedScope": descriptor_data.get("requiresVerifiedScope", False),
                "categories": descriptor_data.get("categories", []),
                "categoryText": descriptor_data.get("categoryText", "Remote source"),
            })

    osint_manager = getattr(container, "osint_manager", None)
    osint_registry = getattr(osint_manager, "registry", None)
    if osint_registry is not None:
        for connector in tuple(osint_registry.all()):
            name = str(getattr(connector, "name", "") or connector.__class__.__name__).strip()
            capabilities = sorted(
                _enum_value(item)
                for item in getattr(connector, "supported_targets", ()) or ()
            )
            available = _call_bool(connector, "is_available", True)
            rows.append({
                "id": f"osint:{name.casefold()}",
                "code": name,
                "title": name,
                "subsystem": "Classic OSINT",
                "kind": "osint_connector",
                "runtimeStatus": "Ready" if available else "Unavailable",
                "implementationStatus": "existing_connector",
                "configured": available,
                "automatic": True,
                "searchable": False,
                "routePage": "osint",
                "capabilities": capabilities,
                "capabilitiesText": ", ".join(capabilities),
                "countries": [],
                "countriesText": "GLOBAL",
                "accessMode": "connector",
                "cost": "free_or_external",
                "sensitivity": "public",
                "documentationUrl": "",
                "notes": str(getattr(connector, "description", "") or ""),
                "requiresCredentials": not available,
                "requiresVerifiedScope": False,
                "categories": ["web_osint"],
                "categoryText": "Classic OSINT",
            })

    registry_registry = getattr(container, "registry_provider_registry", None)
    if registry_registry is not None:
        for provider in tuple(registry_registry.all()):
            info = getattr(provider, "info", None)
            if info is None:
                continue
            name = str(getattr(info, "name", "") or provider.__class__.__name__).strip().casefold()
            display_name = str(getattr(info, "display_name", "") or _title(name))
            capabilities = sorted(_enum_value(item) for item in getattr(info, "query_kinds", ()) or ())
            countries = sorted(str(item) for item in getattr(info, "countries", ()) or ())
            configured = not bool(getattr(info, "requires_credentials", False)) or _call_bool(provider, "is_available", False)
            rows.append({
                "id": f"registry:{name}",
                "code": name,
                "title": display_name,
                "subsystem": "Registry",
                "kind": "registry_provider",
                "runtimeStatus": "Ready" if configured else "Needs configuration",
                "implementationStatus": "active",
                "configured": configured,
                "automatic": bool(getattr(info, "automatic_eligible", False)),
                "searchable": False,
                "routePage": "registry",
                "capabilities": capabilities,
                "capabilitiesText": ", ".join(capabilities),
                "countries": countries,
                "countriesText": "GLOBAL" if bool(getattr(info, "global_scope", False)) else ", ".join(countries),
                "accessMode": _enum_value(getattr(info, "access_mode", None)),
                "cost": "free_or_configured",
                "sensitivity": "public_sensitive" if bool(getattr(info, "sensitive_legal_data", False)) else "public",
                "documentationUrl": "",
                "notes": "Registry provider. Use Registry Intelligence for provider-aware identity and legal safety handling.",
                "requiresCredentials": bool(getattr(info, "requires_credentials", False)),
                "requiresVerifiedScope": False,
                "categories": ["registry"],
                "categoryText": "Registry",
            })

    open_web_registry = getattr(container, "open_web_provider_registry", None)
    if open_web_registry is not None:
        for provider in tuple(open_web_registry.all()):
            info = getattr(provider, "info", None)
            if info is None:
                continue
            name = str(getattr(info, "name", "") or provider.__class__.__name__).strip().casefold()
            display_name = str(getattr(info, "display_name", "") or _title(name))
            capabilities = sorted(_enum_value(item) for item in getattr(info, "supported_targets", ()) or ())
            available = _call_bool(provider, "is_available", not bool(getattr(info, "requires_credentials", False)))
            rows.append({
                "id": f"openweb:{name}",
                "code": name,
                "title": display_name,
                "subsystem": "Open Web",
                "kind": "open_web_provider",
                "runtimeStatus": "Ready" if available else "Unavailable",
                "implementationStatus": "active",
                "configured": available,
                "automatic": bool(getattr(info, "automatic_eligible", False)),
                "searchable": False,
                "routePage": "osint",
                "capabilities": capabilities,
                "capabilitiesText": ", ".join(capabilities),
                "countries": [],
                "countriesText": "GLOBAL",
                "accessMode": "public_automated" if bool(getattr(info, "public_data_only", True)) else "restricted",
                "cost": "free_or_external",
                "sensitivity": "public",
                "documentationUrl": "",
                "notes": "Open-Web discovery provider used by recursive OSINT enrichment.",
                "requiresCredentials": bool(getattr(info, "requires_credentials", False)),
                "requiresVerifiedScope": False,
                "categories": ["web_osint"],
                "categoryText": "Open Web",
            })

    if catalog is not None:
        for descriptor in tuple(catalog.all()):
            code = str(getattr(descriptor, "code", "") or "").strip().casefold()
            if not code or code in seen_catalog_codes:
                continue
            entry = coverage.get(code) if coverage is not None else None
            implementation_status = _enum_value(getattr(entry, "status", None)) or "cataloged"
            if implementation_status not in {"cataloged", "manual_assisted"}:
                continue
            data = _descriptor_row(descriptor)
            rows.append({
                "id": f"catalog:{code}",
                "code": code,
                "title": data["title"] or _title(code),
                "subsystem": "Catalog",
                "kind": "catalog_only",
                "runtimeStatus": "Manual" if implementation_status == "manual_assisted" else "Catalog only",
                "implementationStatus": implementation_status,
                "configured": False,
                "automatic": False,
                "searchable": False,
                "routePage": "sources",
                **data,
            })

    rows.sort(key=lambda item: (str(item.get("subsystem") or ""), str(item.get("title") or "").casefold()))

    federation_rows = [item for item in rows if item["kind"] == "remote_adapter"]
    capability_codes = sorted({cap for item in federation_rows for cap in item.get("capabilities", [])})
    ready = sum(1 for item in rows if item.get("configured"))
    searchable = sum(1 for item in rows if item.get("searchable"))

    return {
        "sources": rows,
        "capabilityCodes": capability_codes,
        "capabilityLabels": [_title(code) for code in capability_codes],
        "counts": {
            "total": len(rows),
            "ready": ready,
            "searchable": searchable,
            "remoteAdapters": len(federation_rows),
            "classicConnectors": sum(1 for item in rows if item["kind"] == "osint_connector"),
            "registryProviders": sum(1 for item in rows if item["kind"] == "registry_provider"),
            "openWebProviders": sum(1 for item in rows if item["kind"] == "open_web_provider"),
            "catalogOnly": sum(1 for item in rows if item["kind"] == "catalog_only"),
            "capabilities": len(capability_codes),
        },
    }
