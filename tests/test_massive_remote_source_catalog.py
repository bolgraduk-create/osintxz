from __future__ import annotations

from app.intelligence_sources.builtin_sources import (
    COVERAGE_ENTRIES,
    MASSIVE_REMOTE_SOURCES,
    register_massive_remote_sources,
)
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.contracts import (
    IntelligenceAccessMode,
    IntelligenceSourceCategory,
)
from app.intelligence_sources.coverage import SourceImplementationStatus


def test_massive_catalog_has_broad_coverage():
    assert len(MASSIVE_REMOTE_SOURCES) >= 45
    codes = {source.code for source in MASSIVE_REMOTE_SOURCES}
    assert len(codes) == len(MASSIVE_REMOTE_SOURCES)


def test_all_sources_are_remote_query_and_not_bulk_required():
    assert all(item.remote_query_supported for item in MASSIVE_REMOTE_SOURCES)
    assert all(not item.bulk_download_required for item in MASSIVE_REMOTE_SOURCES)


def test_catalog_spans_core_intelligence_categories():
    categories = set()
    for item in MASSIVE_REMOTE_SOURCES:
        categories.update(item.categories)
    expected = {
        IntelligenceSourceCategory.REGISTRY,
        IntelligenceSourceCategory.OPEN_DATA,
        IntelligenceSourceCategory.WEB_OSINT,
        IntelligenceSourceCategory.ARCHIVE,
        IntelligenceSourceCategory.BREACH_INTELLIGENCE,
        IntelligenceSourceCategory.DARK_WEB,
        IntelligenceSourceCategory.THREAT_INTELLIGENCE,
        IntelligenceSourceCategory.SANCTIONS,
        IntelligenceSourceCategory.PROCUREMENT,
        IntelligenceSourceCategory.SECURITIES,
        IntelligenceSourceCategory.ACADEMIC,
        IntelligenceSourceCategory.CHARITY,
    }
    assert expected.issubset(categories)


def test_access_modes_are_conservative_for_key_sources():
    items = {item.code: item for item in MASSIVE_REMOTE_SOURCES}
    assert items["us_sec_edgar"].access_mode is IntelligenceAccessMode.NO_AUTH
    assert items["eu_ted_search"].access_mode is IntelligenceAccessMode.NO_AUTH
    assert items["ror"].access_mode is IntelligenceAccessMode.NO_AUTH
    assert items["crossref"].access_mode is IntelligenceAccessMode.NO_AUTH
    assert items["us_sam_entities"].access_mode is IntelligenceAccessMode.FREE_API_KEY
    assert items["au_abn_lookup"].access_mode is IntelligenceAccessMode.FREE_API_KEY
    assert items["pl_regon"].access_mode is IntelligenceAccessMode.FREE_API_KEY


def test_existing_hibp_and_tor_descriptors_are_not_overwritten():
    catalog = IntelligenceSourceCatalog()
    hibp = next(item for item in MASSIVE_REMOTE_SOURCES if item.code == "hibp_pwned_passwords")
    # Replace one field to emulate the more specialized R13.6 descriptor.
    catalog.register(hibp)
    original = catalog.get("hibp_pwned_passwords")
    coverage = register_massive_remote_sources(catalog)
    assert catalog.get("hibp_pwned_passwords") is original
    assert coverage.get("hibp_pwned_passwords") is not None


def test_coverage_distinguishes_active_existing_and_catalog_only():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)
    summary = coverage.summary()
    assert summary["active"] >= 12
    assert summary["existing_connector"] >= 8
    assert summary["cataloged"] >= 20
    assert summary["total"] == len(COVERAGE_ENTRIES)


def test_cataloged_does_not_mean_automatic_execution():
    catalog = IntelligenceSourceCatalog()
    coverage = register_massive_remote_sources(catalog)
    sec = catalog.get("us_sec_edgar")
    assert sec is not None
    assert coverage.get("us_sec_edgar").status is SourceImplementationStatus.CATALOGED
    assert sec.default_enabled is False
    assert sec.automatic_eligible() is False


def test_remote_catalog_can_find_research_sources():
    catalog = IntelligenceSourceCatalog()
    register_massive_remote_sources(catalog)
    research = catalog.find(category=IntelligenceSourceCategory.ACADEMIC)
    codes = {item.code for item in research}
    assert {"crossref", "ror", "openalex", "orcid_public"}.issubset(codes)
