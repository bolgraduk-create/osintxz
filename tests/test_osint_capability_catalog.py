from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.osint.capabilities import (
    ConnectorDisposition,
    DiscoveryGoal,
    NetworkMode,
    OSINT_CAPABILITY_CATALOG,
    capabilities_for_goal,
    capabilities_for_target,
)
from app.osint.models import OsintTargetType


CONNECTOR_DIR = Path("app/osint/connectors")


def _connector_module_stems() -> set[str]:
    return {
        path.stem
        for path in CONNECTOR_DIR.glob("*_connector.py")
    }


def _manager_registered_classes() -> set[str]:
    source = Path("app/osint/manager.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "connectors"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.List):
            continue

        for element in node.value.elts:
            if (
                isinstance(element, ast.Call)
                and isinstance(element.func, ast.Name)
            ):
                classes.add(element.func.id)

    return classes


def test_catalog_covers_every_connector_module_in_repository() -> None:
    assert set(OSINT_CAPABILITY_CATALOG) == _connector_module_stems()


def test_manager_registration_flags_match_current_manager() -> None:
    registered = _manager_registered_classes()

    catalog_registered = {
        capability.connector_class
        for capability in OSINT_CAPABILITY_CATALOG.values()
        if capability.manager_default_registered
    }

    assert catalog_registered == registered


def test_no_credentialed_or_active_separate_connector_is_default_enabled() -> None:
    for capability in OSINT_CAPABILITY_CATALOG.values():
        if not capability.default_enabled:
            continue

        assert not capability.requires_account
        assert not capability.requires_api_key
        assert capability.disposition not in {
            ConnectorDisposition.CONDITIONAL,
            ConnectorDisposition.SEPARATE,
            ConnectorDisposition.REPLACE,
        }
        assert capability.network_mode is not NetworkMode.ACTIVE


def test_phoneinfoga_is_support_not_account_discovery_core() -> None:
    capability = OSINT_CAPABILITY_CATALOG["phoneinfoga_connector"]

    assert capability.disposition is ConnectorDisposition.SUPPORT
    assert DiscoveryGoal.PHONE_ENRICHMENT in capability.goals
    assert DiscoveryGoal.ACCOUNT_DISCOVERY not in capability.goals
    assert capability.creates_new_entities is False
    assert capability.recursive_value <= 1


def test_ghunt_is_optional_authenticated_enrichment() -> None:
    capability = OSINT_CAPABILITY_CATALOG["ghunt_connector"]

    assert capability.disposition is ConnectorDisposition.CONDITIONAL
    assert capability.requires_account is True
    assert capability.default_enabled is False


def test_whatsmyname_legacy_connector_is_marked_for_replacement() -> None:
    capability = OSINT_CAPABILITY_CATALOG["whatsmyname_connector"]

    assert capability.disposition is ConnectorDisposition.REPLACE
    assert capability.manager_default_registered is False
    assert capability.default_enabled is False


@pytest.mark.parametrize(
    "module",
    [
        "nmap_connector",
        "naabu_connector",
        "nuclei_connector",
        "nikto_connector",
        "ffuf_connector",
        "feroxbuster_connector",
    ],
)
def test_active_assessment_tools_are_never_automatic_osint_defaults(module: str) -> None:
    capability = OSINT_CAPABILITY_CATALOG[module]

    assert capability.disposition is ConnectorDisposition.SEPARATE
    assert capability.default_enabled is False
    assert capability.network_mode is NetworkMode.ACTIVE


def test_username_default_account_discovery_has_two_independent_core_sources() -> None:
    capabilities = capabilities_for_goal(
        DiscoveryGoal.ACCOUNT_DISCOVERY,
        default_only=True,
    )

    names = {item.display_name for item in capabilities}
    assert {"Maigret", "Sherlock"}.issubset(names)


def test_phone_current_default_route_is_enrichment_only() -> None:
    capabilities = capabilities_for_target(
        OsintTargetType.PHONE,
        default_only=True,
    )

    assert [item.display_name for item in capabilities] == ["Local Phone", "PhoneInfoga"]
    assert all(
        DiscoveryGoal.PHONE_ENRICHMENT in item.goals
        for item in capabilities
    )


def test_domain_default_catalog_contains_recursive_discovery_sources() -> None:
    capabilities = capabilities_for_target(
        OsintTargetType.DOMAIN,
        default_only=True,
    )

    names = {item.display_name for item in capabilities}
    assert {"crt.sh", "Common Crawl", "Subfinder", "Waybackurls", "GAU"}.issubset(names)


def test_every_catalog_entry_has_nonempty_machine_readable_contract() -> None:
    for module, capability in OSINT_CAPABILITY_CATALOG.items():
        assert module.endswith("_connector")
        assert capability.connector_class.endswith("Connector")
        assert capability.display_name.strip()
        assert capability.input_types
        assert capability.goals
        assert capability.output_capabilities
        assert 0 <= capability.recursive_value <= 5
