from __future__ import annotations

from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.contracts import (
    DataSensitivity,
    IntelligenceAccessMode as Access,
    IntelligenceCost as Cost,
    IntelligenceDeliveryMode as Delivery,
    IntelligenceSourceCategory as Category,
    IntelligenceSourceDescriptor as Source,
    IntelligenceSourceOrigin as Origin,
    IntelligenceTransport as Transport,
)
from app.intelligence_sources.coverage import (
    RemoteSourceCoverage,
    SourceCoverageEntry,
    SourceImplementationStatus as Status,
)


def _source(
    code: str,
    name: str,
    *,
    categories: set[Category],
    capabilities: set[str],
    transport: Transport = Transport.REST,
    access: Access = Access.NO_AUTH,
    cost: Cost = Cost.FREE,
    origin: Origin = Origin.OTHER,
    countries: set[str] | None = None,
    global_scope: bool = False,
    requires_credentials: bool = False,
    default_enabled: bool = False,
    sensitivity: DataSensitivity = DataSensitivity.PUBLIC,
    documentation_url: str | None = None,
    terms_url: str | None = None,
    notes: str = "",
) -> Source:
    return Source(
        code=code,
        display_name=name,
        categories=frozenset(categories),
        capabilities=frozenset(capabilities),
        transport=transport,
        access_mode=access,
        cost=cost,
        delivery_mode=Delivery.REMOTE_QUERY,
        origin=origin,
        countries=frozenset(countries or set()),
        global_scope=global_scope,
        requires_credentials=requires_credentials,
        default_enabled=default_enabled,
        remote_query_supported=True,
        bulk_download_required=False,
        default_sensitivity=sensitivity,
        raw_secret_storage_allowed=False,
        redistribution_allowed=False,
        documentation_url=documentation_url,
        terms_url=terms_url,
        notes=notes,
    )


# Catalog metadata is deliberately conservative. A descriptor means OSINTXZ
# knows the source/capabilities/access policy; it does NOT claim that a query
# adapter is implemented unless coverage status says ACTIVE/EXISTING_CONNECTOR.
MASSIVE_REMOTE_SOURCES: tuple[Source, ...] = (
    # ---------------- Existing Registry / Breach / Dark Web ----------------
    _source("gleif_lei", "GLEIF LEI API", categories={Category.REGISTRY, Category.FINANCIAL}, capabilities={"lei", "name", "organization"}, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://www.gleif.org/en/lei-data/gleif-api"),
    _source("eu_vies", "EU VIES VAT Validation", categories={Category.REGISTRY}, capabilities={"vat_id", "vat_validation"}, origin=Origin.OFFICIAL_API, global_scope=True, default_enabled=True, documentation_url="https://ec.europa.eu/taxation_customs/vies/"),
    _source("opencorporates", "OpenCorporates", categories={Category.REGISTRY}, capabilities={"company_name", "registration_id"}, access=Access.CONTRACT, cost=Cost.MIXED, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://api.opencorporates.com/"),
    _source("ua_edr_business", "Ukraine EDR Business", categories={Category.REGISTRY}, capabilities={"company_name", "registration_id", "sole_trader"}, transport=Transport.REMOTE_BACKEND, origin=Origin.OFFICIAL_OPEN_DATA, countries={"UA"}),
    _source("ua_edrsr", "Ukraine EDRSR Court Decisions", categories={Category.REGISTRY}, capabilities={"case_number", "court_decision"}, transport=Transport.REMOTE_BACKEND, origin=Origin.OFFICIAL_OPEN_DATA, countries={"UA"}, sensitivity=DataSensitivity.PUBLIC_SENSITIVE),
    _source("courtlistener", "CourtListener Case Law", categories={Category.REGISTRY}, capabilities={"case_number", "case_name", "court_decision"}, access=Access.FREE_API_KEY, origin=Origin.AGGREGATOR, countries={"US"}, requires_credentials=True, documentation_url="https://www.courtlistener.com/help/api/rest/"),
    _source("courtlistener_recap", "CourtListener RECAP", categories={Category.REGISTRY}, capabilities={"case_number", "federal_docket"}, access=Access.FREE_API_KEY, origin=Origin.AGGREGATOR, countries={"US"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.courtlistener.com/help/api/rest/"),
    _source("uk_companies_house", "UK Companies House", categories={Category.REGISTRY}, capabilities={"company_name", "registration_id"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"GB"}, requires_credentials=True, documentation_url="https://developer.company-information.service.gov.uk/"),
    _source("pl_krs", "Poland KRS", categories={Category.REGISTRY}, capabilities={"registration_id", "company"}, origin=Origin.OFFICIAL_OPEN_DATA, countries={"PL"}, default_enabled=True, documentation_url="https://api-krs.ms.gov.pl/"),
    _source("hibp_breached_account", "Have I Been Pwned — Breached Account", categories={Category.BREACH_INTELLIGENCE}, capabilities={"email", "breach_lookup"}, access=Access.CONTRACT, cost=Cost.MIXED, origin=Origin.BREACH_PROVIDER, global_scope=True, requires_credentials=True, sensitivity=DataSensitivity.BREACH_METADATA, documentation_url="https://haveibeenpwned.com/API/v3"),
    _source("hibp_pwned_passwords", "Have I Been Pwned — Pwned Passwords", categories={Category.BREACH_INTELLIGENCE}, capabilities={"password_exposure"}, origin=Origin.BREACH_PROVIDER, global_scope=True, default_enabled=True, sensitivity=DataSensitivity.BREACH_METADATA, documentation_url="https://haveibeenpwned.com/API/v3"),
    _source("tor_public_onion_fetch", "Tor Public Onion Fetch", categories={Category.DARK_WEB}, capabilities={"onion_url", "email", "domain", "username", "crypto_address", "public_page_observation"}, transport=Transport.TOR_HTTP, origin=Origin.DARKWEB_PUBLICATION, global_scope=True, sensitivity=DataSensitivity.DARKWEB_PUBLIC, documentation_url="https://support.torproject.org/tor-browser/features/onion-services/"),

    # ---------------- Existing OSINT connectors / remote web sources --------
    _source("common_crawl", "Common Crawl Index", categories={Category.ARCHIVE, Category.WEB_OSINT}, capabilities={"url", "domain", "historical_web"}, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://index.commoncrawl.org/"),
    _source("crt_sh", "crt.sh Certificate Transparency", categories={Category.WEB_OSINT}, capabilities={"domain", "certificate", "subdomain"}, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://crt.sh/"),
    _source("urlscan", "urlscan.io", categories={Category.THREAT_INTELLIGENCE, Category.WEB_OSINT}, capabilities={"url", "domain", "ip", "scan"}, access=Access.FREE_API_KEY, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://urlscan.io/docs/api/"),
    _source("virustotal", "VirusTotal", categories={Category.THREAT_INTELLIGENCE}, capabilities={"domain", "url", "ip", "hash"}, access=Access.FREE_API_KEY, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://docs.virustotal.com/reference/overview"),
    _source("alienvault_otx", "AlienVault OTX", categories={Category.THREAT_INTELLIGENCE}, capabilities={"domain", "url", "ip", "hash", "pulse"}, access=Access.FREE_API_KEY, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://otx.alienvault.com/api"),
    _source("greynoise", "GreyNoise", categories={Category.THREAT_INTELLIGENCE}, capabilities={"ip", "internet_scanner_context"}, access=Access.FREE_API_KEY, cost=Cost.MIXED, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://docs.greynoise.io/"),
    _source("abuseipdb", "AbuseIPDB", categories={Category.THREAT_INTELLIGENCE}, capabilities={"ip", "abuse_report"}, access=Access.FREE_API_KEY, cost=Cost.MIXED, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, documentation_url="https://docs.abuseipdb.com/"),
    _source("bgpview", "BGPView", categories={Category.THREAT_INTELLIGENCE, Category.WEB_OSINT}, capabilities={"ip", "asn", "prefix", "organization"}, origin=Origin.AGGREGATOR, global_scope=True, documentation_url="https://bgpview.io/"),
    _source("wayback_cdx", "Internet Archive Wayback CDX", categories={Category.ARCHIVE, Category.WEB_OSINT}, capabilities={"url", "domain", "historical_web"}, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://web.archive.org/"),
    _source("gdelt", "GDELT", categories={Category.OPEN_DATA, Category.WEB_OSINT}, capabilities={"news", "name", "domain", "event"}, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://www.gdeltproject.org/"),

    # ---------------- New official / open remote candidates -----------------
    _source("us_sec_edgar", "US SEC EDGAR", categories={Category.SECURITIES, Category.FINANCIAL, Category.REGISTRY}, capabilities={"cik", "company_filings", "xbrl", "securities"}, origin=Origin.OFFICIAL_API, countries={"US"}, documentation_url="https://www.sec.gov/search-filings/edgar-application-programming-interfaces"),
    _source("us_sam_entities", "SAM.gov Entity Management", categories={Category.REGISTRY, Category.PROCUREMENT}, capabilities={"uei", "entity", "registration_id", "company_name"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, documentation_url="https://open.gsa.gov/api/entity-api/"),
    _source("us_sam_exclusions", "SAM.gov Exclusions", categories={Category.SANCTIONS, Category.PROCUREMENT}, capabilities={"name", "uei", "exclusion"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://open.gsa.gov/api/exclusions-api/"),
    _source("us_sam_opportunities", "SAM.gov Contract Opportunities", categories={Category.PROCUREMENT}, capabilities={"notice", "organization", "solicitation", "procurement"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, documentation_url="https://open.gsa.gov/api/get-opportunities-public-api/"),
    _source("us_trade_csl", "US Consolidated Screening List", categories={Category.SANCTIONS}, capabilities={"name", "organization", "person", "screening", "fuzzy_name"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.trade.gov/consolidated-screening-list"),
    _source("eu_ted_search", "EU TED Procurement Search", categories={Category.PROCUREMENT, Category.OPEN_DATA}, capabilities={"notice", "buyer", "supplier", "procurement", "organization"}, origin=Origin.OFFICIAL_API, global_scope=True, documentation_url="https://docs.ted.europa.eu/api/latest/search.html"),
    _source("no_brreg_entities", "Norway Brønnøysund Entity Register", categories={Category.REGISTRY}, capabilities={"organization_number", "company_name", "organization"}, origin=Origin.OFFICIAL_API, countries={"NO"}, documentation_url="https://data.brreg.no/enhetsregisteret/api/dokumentasjon/en/index.html"),
    _source("no_brreg_roles", "Norway Brønnøysund Roles", categories={Category.REGISTRY, Category.PUBLIC_OFFICIAL}, capabilities={"organization_number", "role", "person", "organization"}, origin=Origin.OFFICIAL_API, countries={"NO"}, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://data.brreg.no/"),
    _source("cz_ares", "Czech ARES", categories={Category.REGISTRY}, capabilities={"ico", "company_name", "organization", "address"}, origin=Origin.OFFICIAL_API, countries={"CZ"}, documentation_url="https://ares.gov.cz/"),
    _source("fr_sirene", "France SIRENE / API Entreprise", categories={Category.REGISTRY}, capabilities={"siren", "siret", "organization", "establishment"}, access=Access.FREE_ACCOUNT, origin=Origin.OFFICIAL_API, countries={"FR"}, requires_credentials=True, documentation_url="https://entreprise.api.gouv.fr/"),
    _source("au_abn_lookup", "Australia ABN Lookup", categories={Category.REGISTRY}, capabilities={"abn", "acn", "company_name", "organization"}, transport=Transport.SOAP, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"AU"}, requires_credentials=True, documentation_url="https://abr.business.gov.au/Documentation/Default"),
    _source("ca_federal_corporations", "Corporations Canada Federal Corporation API", categories={Category.REGISTRY}, capabilities={"corporation_id", "business_number", "company", "director"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"CA"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api.ised-isde.canada.ca/en/docs?api=corporations"),
    _source("uk_charity_commission", "UK Charity Commission Register", categories={Category.CHARITY, Category.REGISTRY}, capabilities={"charity_name", "charity_number", "trustee", "organization"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"GB"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api-portal.charitycommission.gov.uk/"),
    _source("uk_sanctions_search", "UK Sanctions List Search", categories={Category.SANCTIONS}, capabilities={"name", "organization", "person", "ship", "sanctions"}, transport=Transport.PUBLIC_HTTP, access=Access.MANUAL_ASSISTED, origin=Origin.OFFICIAL_PORTAL, countries={"GB"}, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.gov.uk/government/publications/the-uk-sanctions-list"),
    _source("pl_regon", "Poland REGON BIR1", categories={Category.REGISTRY}, capabilities={"regon", "nip", "krs", "organization"}, transport=Transport.SOAP, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"PL"}, requires_credentials=True, documentation_url="https://api.stat.gov.pl/Home/RegonApi?lang=en"),
    _source("crossref", "Crossref REST API", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"doi", "work", "author", "funder", "orcid", "ror", "publication"}, origin=Origin.AGGREGATOR, global_scope=True, documentation_url="https://www.crossref.org/documentation/retrieve-metadata/rest-api/"),
    _source("ror", "Research Organization Registry", categories={Category.ACADEMIC, Category.REGISTRY}, capabilities={"organization", "ror_id", "affiliation", "name"}, origin=Origin.AGGREGATOR, global_scope=True, documentation_url="https://ror.readme.io/docs/rest-api"),
    _source("openalex", "OpenAlex", categories={Category.ACADEMIC, Category.OPEN_DATA}, capabilities={"work", "author", "institution", "source", "topic", "name"}, origin=Origin.AGGREGATOR, global_scope=True, documentation_url="https://help.openalex.org/api/"),
    _source("orcid_public", "ORCID Public API", categories={Category.ACADEMIC}, capabilities={"orcid", "researcher", "works", "affiliation"}, access=Access.FREE_ACCOUNT, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://info.orcid.org/documentation/integration-guide/"),
    _source("wikidata_sparql", "Wikidata Query Service", categories={Category.OPEN_DATA, Category.WEB_OSINT}, capabilities={"person", "organization", "identifier", "relationship", "location", "name"}, transport=Transport.SPARQL, origin=Origin.COMMUNITY_INDEX, global_scope=True, documentation_url="https://query.wikidata.org/"),
    _source("nvd_cve_api", "NIST NVD CVE API", categories={Category.THREAT_INTELLIGENCE, Category.OPEN_DATA}, capabilities={"cve", "cpe", "vulnerability", "product"}, origin=Origin.OFFICIAL_API, countries={"US"}, documentation_url="https://nvd.nist.gov/developers/vulnerabilities"),
    _source("openfda", "openFDA", categories={Category.OPEN_DATA, Category.PROFESSIONAL}, capabilities={"manufacturer", "product", "device", "drug", "enforcement"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, documentation_url="https://open.fda.gov/apis/"),
    _source("us_fec", "US Federal Election Commission API", categories={Category.PUBLIC_OFFICIAL, Category.OPEN_DATA}, capabilities={"candidate", "committee", "organization", "contribution"}, access=Access.FREE_API_KEY, origin=Origin.OFFICIAL_API, countries={"US"}, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://api.open.fec.gov/developers/"),
    _source("opensanctions", "OpenSanctions", categories={Category.SANCTIONS, Category.PUBLIC_OFFICIAL}, capabilities={"person", "organization", "sanctions", "pep", "name"}, access=Access.FREE_API_KEY, cost=Cost.MIXED, origin=Origin.AGGREGATOR, global_scope=True, requires_credentials=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://www.opensanctions.org/docs/api/"),
    _source("icij_offshore_leaks", "ICIJ Offshore Leaks Database", categories={Category.OPEN_DATA, Category.REGISTRY}, capabilities={"person", "organization", "offshore_entity", "officer", "intermediary", "address"}, transport=Transport.PUBLIC_HTTP, access=Access.MANUAL_ASSISTED, origin=Origin.COMMUNITY_INDEX, global_scope=True, sensitivity=DataSensitivity.PUBLIC_SENSITIVE, documentation_url="https://offshoreleaks.icij.org/"),
)


COVERAGE_ENTRIES: tuple[SourceCoverageEntry, ...] = (
    SourceCoverageEntry("gleif_lei", Status.ACTIVE, "GleifRegistryProvider", "R6"),
    SourceCoverageEntry("eu_vies", Status.ACTIVE, "ViesRegistryProvider", "R7"),
    SourceCoverageEntry("opencorporates", Status.ACTIVE, "OpenCorporatesRegistryProvider", "R5"),
    SourceCoverageEntry("ua_edr_business", Status.ACTIVE, "RemoteRegistryProvider", "R8"),
    SourceCoverageEntry("ua_edrsr", Status.ACTIVE, "RemoteRegistryProvider", "R9"),
    SourceCoverageEntry("courtlistener", Status.ACTIVE, "CourtListenerRegistryProvider", "R10"),
    SourceCoverageEntry("courtlistener_recap", Status.ACTIVE, "CourtListenerRecapRegistryProvider", "R11"),
    SourceCoverageEntry("uk_companies_house", Status.ACTIVE, "CompaniesHouseRegistryProvider", "R12"),
    SourceCoverageEntry("pl_krs", Status.ACTIVE, "PolandKrsRegistryProvider", "R13"),
    SourceCoverageEntry("hibp_breached_account", Status.ACTIVE, "BreachIntelligenceService", "R13.6"),
    SourceCoverageEntry("hibp_pwned_passwords", Status.ACTIVE, "BreachIntelligenceService", "R13.6"),
    SourceCoverageEntry("tor_public_onion_fetch", Status.ACTIVE, "DarkWebIntelligenceService", "R13.7"),
    SourceCoverageEntry("common_crawl", Status.EXISTING_CONNECTOR, "CommonCrawl/OpenWeb", "existing"),
    SourceCoverageEntry("crt_sh", Status.EXISTING_CONNECTOR, "crt.sh connector", "existing"),
    SourceCoverageEntry("urlscan", Status.EXISTING_CONNECTOR, "URLScan connector", "existing"),
    SourceCoverageEntry("virustotal", Status.EXISTING_CONNECTOR, "VirusTotal connector", "existing"),
    SourceCoverageEntry("alienvault_otx", Status.EXISTING_CONNECTOR, "AlienVault OTX connector", "existing"),
    SourceCoverageEntry("greynoise", Status.EXISTING_CONNECTOR, "GreyNoise connector", "existing"),
    SourceCoverageEntry("abuseipdb", Status.EXISTING_CONNECTOR, "AbuseIPDB connector", "existing"),
    SourceCoverageEntry("bgpview", Status.EXISTING_CONNECTOR, "BGPView connector", "existing"),
    SourceCoverageEntry("wayback_cdx", Status.EXISTING_CONNECTOR, "Wayback connector", "existing"),
    SourceCoverageEntry("gdelt", Status.EXISTING_CONNECTOR, "OpenWeb GDELT", "existing"),
    SourceCoverageEntry("us_sec_edgar", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("us_sam_entities", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("us_sam_exclusions", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("us_sam_opportunities", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("us_trade_csl", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("eu_ted_search", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("no_brreg_entities", Status.CATALOGED, stage="europe"),
    SourceCoverageEntry("no_brreg_roles", Status.CATALOGED, stage="europe"),
    SourceCoverageEntry("cz_ares", Status.CATALOGED, stage="europe"),
    SourceCoverageEntry("fr_sirene", Status.CATALOGED, stage="europe"),
    SourceCoverageEntry("au_abn_lookup", Status.CATALOGED, stage="apac"),
    SourceCoverageEntry("ca_federal_corporations", Status.CATALOGED, stage="americas"),
    SourceCoverageEntry("uk_charity_commission", Status.CATALOGED, stage="next-wave"),
    SourceCoverageEntry("uk_sanctions_search", Status.MANUAL_ASSISTED, stage="next-wave"),
    SourceCoverageEntry("pl_regon", Status.CATALOGED, stage="europe"),
    SourceCoverageEntry("crossref", Status.CATALOGED, stage="research"),
    SourceCoverageEntry("ror", Status.CATALOGED, stage="research"),
    SourceCoverageEntry("openalex", Status.CATALOGED, stage="research"),
    SourceCoverageEntry("orcid_public", Status.CATALOGED, stage="research"),
    SourceCoverageEntry("wikidata_sparql", Status.CATALOGED, stage="global-open-data"),
    SourceCoverageEntry("nvd_cve_api", Status.CATALOGED, stage="threat-intel"),
    SourceCoverageEntry("openfda", Status.CATALOGED, stage="us-open-data"),
    SourceCoverageEntry("us_fec", Status.CATALOGED, stage="us-open-data"),
    SourceCoverageEntry("opensanctions", Status.CATALOGED, stage="sanctions"),
    SourceCoverageEntry("icij_offshore_leaks", Status.MANUAL_ASSISTED, stage="investigative-data"),
)


def register_massive_remote_sources(
    catalog: IntelligenceSourceCatalog,
) -> RemoteSourceCoverage:
    for source in MASSIVE_REMOTE_SOURCES:
        # R13.6/R13.7 may already have more specialized HIBP/Tor descriptors.
        # Preserve the existing installed descriptor instead of overwriting it.
        if catalog.get(source.code) is None:
            catalog.register(source)
    return RemoteSourceCoverage(COVERAGE_ENTRIES)
