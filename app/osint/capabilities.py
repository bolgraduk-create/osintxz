"""
Machine-readable OSINT connector capability catalog.

M021.0.1 purpose
----------------
Describe what every OSINT connector in the repository is *for* before
Investigation Engine automatic pivot routing is enabled.

This module does not execute connectors. It is a policy/metadata layer only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from app.osint.models import OsintTargetType


class ConnectorDisposition(str, Enum):
    """Product role assigned by the capability audit."""

    CORE = "core"
    SUPPORT = "support"
    CONDITIONAL = "conditional"
    SEPARATE = "separate"
    REPLACE = "replace"


class DiscoveryGoal(str, Enum):
    """High-level goal used later by the M021 pivot router."""

    ACCOUNT_DISCOVERY = "account_discovery"
    EMAIL_REGISTRATION = "email_registration"
    EMAIL_PROFILE_ENRICHMENT = "email_profile_enrichment"
    PHONE_ENRICHMENT = "phone_enrichment"
    OPEN_WEB_DISCOVERY = "open_web_discovery"
    DOMAIN_DISCOVERY = "domain_discovery"
    HISTORICAL_WEB = "historical_web"
    WEB_CRAWL = "web_crawl"
    WEB_METADATA = "web_metadata"
    NETWORK_ENRICHMENT = "network_enrichment"
    THREAT_INTELLIGENCE = "threat_intelligence"
    FILE_REPUTATION = "file_reputation"
    SECRET_DISCOVERY = "secret_discovery"
    CLOUD_DISCOVERY = "cloud_discovery"
    TLS_ANALYSIS = "tls_analysis"
    TECHNOLOGY_FINGERPRINT = "technology_fingerprint"
    VULNERABILITY_ASSESSMENT = "vulnerability_assessment"
    CONTENT_DISCOVERY = "content_discovery"
    VISUALIZATION = "visualization"
    AUTOMATED_OSINT = "automated_osint"
    GOOGLE_ACCOUNT_ENRICHMENT = "google_account_enrichment"


class NetworkMode(str, Enum):
    """Operational character of a connector."""

    PASSIVE = "passive"
    PASSIVE_REMOTE = "passive_remote"
    ACTIVE = "active"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class OsintConnectorCapability:
    """
    Product-facing capability metadata for one connector implementation.

    `default_enabled` means "eligible for automatic enrichment once M021 routing
    is enabled". It does not mean that the tool is installed or available.
    """

    module: str
    connector_class: str
    display_name: str
    input_types: frozenset[OsintTargetType]
    goals: frozenset[DiscoveryGoal]
    output_capabilities: frozenset[str]
    disposition: ConnectorDisposition
    network_mode: NetworkMode

    creates_new_entities: bool
    recursive_value: int  # 0..5
    default_enabled: bool

    requires_account: bool = False
    requires_api_key: bool = False
    manager_default_registered: bool = True

    notes: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.recursive_value <= 5:
            raise ValueError("recursive_value must be between 0 and 5")

        if self.default_enabled and (
            self.requires_account
            or self.requires_api_key
            or self.disposition
            in {
                ConnectorDisposition.CONDITIONAL,
                ConnectorDisposition.SEPARATE,
                ConnectorDisposition.REPLACE,
            }
        ):
            raise ValueError(
                f"{self.display_name}: conditional/separate/credentialed "
                "connectors cannot be default-enabled"
            )

        if (
            self.default_enabled
            and self.network_mode is NetworkMode.ACTIVE
        ):
            raise ValueError(
                f"{self.display_name}: active connectors cannot be "
                "automatic enrichment defaults"
            )


def _c(
    module: str,
    connector_class: str,
    display_name: str,
    inputs: tuple[OsintTargetType, ...],
    goals: tuple[DiscoveryGoal, ...],
    outputs: tuple[str, ...],
    disposition: ConnectorDisposition,
    network_mode: NetworkMode,
    *,
    creates_new_entities: bool,
    recursive_value: int,
    default_enabled: bool,
    requires_account: bool = False,
    requires_api_key: bool = False,
    manager_default_registered: bool = True,
    notes: str = "",
) -> OsintConnectorCapability:
    return OsintConnectorCapability(
        module=module,
        connector_class=connector_class,
        display_name=display_name,
        input_types=frozenset(inputs),
        goals=frozenset(goals),
        output_capabilities=frozenset(outputs),
        disposition=disposition,
        network_mode=network_mode,
        creates_new_entities=creates_new_entities,
        recursive_value=recursive_value,
        default_enabled=default_enabled,
        requires_account=requires_account,
        requires_api_key=requires_api_key,
        manager_default_registered=manager_default_registered,
        notes=notes,
    )


_CAPABILITIES = (
    # ------------------------------------------------------------------
    # Identity / social discovery
    # ------------------------------------------------------------------
    _c(
        "sherlock_connector", "SherlockConnector", "Sherlock",
        (OsintTargetType.USERNAME,),
        (DiscoveryGoal.ACCOUNT_DISCOVERY,),
        ("public_profile_url", "account_presence", "website"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
        notes="Independent username account-discovery signal.",
    ),
    _c(
        "maigret_connector", "MaigretConnector", "Maigret",
        (OsintTargetType.USERNAME,),
        (DiscoveryGoal.ACCOUNT_DISCOVERY,),
        ("public_profile_url", "account_presence", "profile_metadata", "related_identifier"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=5, default_enabled=True,
        notes="Primary username discovery source; high recursive pivot value.",
    ),
    _c(
        "holehe_connector", "HoleheConnector", "Holehe",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.EMAIL_REGISTRATION,),
        ("service_registration_signal", "service_domain"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=2, default_enabled=True,
        notes="Registration-presence signal; usually not a public profile finder.",
    ),
    _c(
        "gravatar_connector", "GravatarConnector", "Gravatar",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.EMAIL_PROFILE_ENRICHMENT,),
        (
            "public_profile_metadata",
            "public_profile_url",
            "verified_account_url",
        ),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
        notes=(
            "Official public profile source. Only explicit Gravatar "
            "verified_accounts are promoted as account URL pivots."
        ),
        manager_default_registered=False,
    ),
    _c(
        "socialscan_connector", "SocialScanConnector", "SocialScan",
        (OsintTargetType.USERNAME, OsintTargetType.EMAIL),
        (DiscoveryGoal.ACCOUNT_DISCOVERY, DiscoveryGoal.EMAIL_REGISTRATION),
        ("service_presence", "service_domain"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=2, default_enabled=True,
        notes="Limited service-presence/availability checks.",
    ),
    _c(
        "user_scanner_connector", "UserScannerConnector", "User Scanner",
        (OsintTargetType.EMAIL, OsintTargetType.USERNAME),
        (
            DiscoveryGoal.EMAIL_REGISTRATION,
            DiscoveryGoal.ACCOUNT_DISCOVERY,
        ),
        (
            "service_registration_signal",
            "service_url",
            "explicit_username",
            "explicit_profile_url",
        ),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=True,
        notes=(
            "Free registration coverage. Automatic mode keeps loud/Hudson/"
            "proxy features disabled and accepts only explicit Registered/"
            "Found results."
        ),
        manager_default_registered=False,
    ),
    _c(
        "local_phone_connector", "LocalPhoneConnector", "Local Phone",
        (OsintTargetType.PHONE,),
        (DiscoveryGoal.PHONE_ENRICHMENT,),
        (
            "canonical_phone", "phone_metadata", "country_region",
            "carrier_metadata", "line_type", "timezone",
            "exact_search_variants",
        ),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
        notes="Primary local phone metadata source; no network and no ownership inference.",
    ),
    _c(
        "phoneinfoga_connector", "PhoneInfogaConnector", "PhoneInfoga",
        (OsintTargetType.PHONE,),
        (DiscoveryGoal.PHONE_ENRICHMENT,),
        ("phone_metadata", "country_region", "carrier_metadata"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=1, default_enabled=True,
        notes="Metadata/enrichment only; not the primary phone account-discovery engine.",
    ),
    _c(
        "ghunt_connector", "GHuntConnector", "GHunt",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.GOOGLE_ACCOUNT_ENRICHMENT,),
        ("google_account_metadata", "public_google_artifacts"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
        requires_account=True,
        notes="Optional user-configured Google-authenticated enrichment.",
    ),
    _c(
        "whatsmyname_connector", "WhatsMyNameConnector", "WhatsMyName",
        (OsintTargetType.USERNAME,),
        (DiscoveryGoal.ACCOUNT_DISCOVERY,),
        ("public_profile_url", "account_presence"),
        ConnectorDisposition.REPLACE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
        manager_default_registered=False,
        notes="Replace legacy CLI expectation with an adapter over the maintained site dataset.",
    ),

    # ------------------------------------------------------------------
    # Domain / asset / open-web discovery
    # ------------------------------------------------------------------
    _c(
        "theharvester_connector", "TheHarvesterConnector", "TheHarvester",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.DOMAIN_DISCOVERY, DiscoveryGoal.OPEN_WEB_DISCOVERY),
        ("email", "hostname", "subdomain", "ip", "public_url"),
        ConnectorDisposition.CORE, NetworkMode.MIXED,
        creates_new_entities=True, recursive_value=5, default_enabled=False,
        notes="Keep, but replace '-b all' with an explicit keyless/passive provider policy before auto-routing.",
    ),
    _c(
        "amass_connector", "AmassConnector", "Amass",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.DOMAIN_DISCOVERY,),
        ("subdomain", "hostname", "ip"),
        ConnectorDisposition.SUPPORT, NetworkMode.MIXED,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
        notes="Useful domain expansion; auto mode waits for passive-only policy.",
    ),
    _c(
        "subfinder_connector", "SubfinderConnector", "Subfinder",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.DOMAIN_DISCOVERY,),
        ("subdomain", "hostname"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
    ),
    _c(
        "dnsx_connector", "DNSXConnector", "DNSX",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.NETWORK_ENRICHMENT,),
        ("dns_record", "ip", "hostname"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=True,
    ),
    _c(
        "crtsh_connector", "CrtShConnector", "crt.sh",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.DOMAIN_DISCOVERY,),
        ("certificate_name", "subdomain", "hostname"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=5, default_enabled=True,
    ),
    _c(
        "assetfinder_connector", "AssetfinderConnector", "Assetfinder",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.DOMAIN_DISCOVERY,),
        ("subdomain", "hostname"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=False,
        manager_default_registered=False,
        notes="Present in repository but not registered by the current OsintManager.",
    ),
    _c(
        "commoncrawl_connector", "CommonCrawlConnector", "Common Crawl",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.OPEN_WEB_DISCOVERY, DiscoveryGoal.HISTORICAL_WEB),
        ("captured_url", "historical_url", "crawl_metadata"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=5, default_enabled=True,
        notes="Core open-web corpus source; content-level discovery adapter remains a later capability.",
    ),
    _c(
        "waybackurls_connector", "WaybackurlsConnector", "Waybackurls",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.HISTORICAL_WEB,),
        ("historical_url",),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
    ),
    _c(
        "gau_connector", "GauConnector", "GAU",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.HISTORICAL_WEB, DiscoveryGoal.OPEN_WEB_DISCOVERY),
        ("historical_url", "public_url"),
        ConnectorDisposition.CORE, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=True,
    ),
    _c(
        "archivetoday_connector", "ArchiveTodayConnector", "Archive.today",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.HISTORICAL_WEB,),
        ("archived_url", "archive_snapshot"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=True,
    ),
    _c(
        "httpx_connector", "HTTPXConnector", "HTTPX",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.WEB_METADATA,),
        ("reachable_url", "http_metadata", "title", "status"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=2, default_enabled=False,
        notes="Directly contacts target hosts; never automatic default enrichment.",
    ),
    _c(
        "katana_connector", "KatanaConnector", "Katana",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.WEB_CRAWL,),
        ("public_url", "endpoint"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
    ),
    _c(
        "hakrawler_connector", "HakrawlerConnector", "Hakrawler",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.WEB_CRAWL,),
        ("public_url", "endpoint"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=3, default_enabled=False,
    ),
    _c(
        "subjs_connector", "SubjsConnector", "Subjs",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.WEB_CRAWL,),
        ("javascript_url", "public_url"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=True,
    ),

    # ------------------------------------------------------------------
    # Network / active assessment (kept outside automatic identity OSINT)
    # ------------------------------------------------------------------
    _c(
        "naabu_connector", "NaabuConnector", "Naabu",
        (OsintTargetType.DOMAIN, OsintTargetType.IP),
        (DiscoveryGoal.NETWORK_ENRICHMENT,),
        ("open_port", "service_endpoint"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        notes="Active network assessment; separate explicit workflow.",
    ),
    _c(
        "nmap_connector", "NmapConnector", "Nmap",
        (OsintTargetType.DOMAIN, OsintTargetType.IP),
        (DiscoveryGoal.NETWORK_ENRICHMENT,),
        ("open_port", "service", "host_metadata"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        notes="Active network assessment; separate explicit workflow.",
    ),
    _c(
        "nuclei_connector", "NucleiConnector", "Nuclei",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.VULNERABILITY_ASSESSMENT,),
        ("template_match", "security_finding"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=0, default_enabled=False,
    ),
    _c(
        "nikto_connector", "NiktoConnector", "Nikto",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.VULNERABILITY_ASSESSMENT,),
        ("security_finding",),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=0, default_enabled=False,
        manager_default_registered=False,
    ),
    _c(
        "ffuf_connector", "FFUFConnector", "FFUF",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.CONTENT_DISCOVERY,),
        ("endpoint", "path"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=1, default_enabled=False,
    ),
    _c(
        "feroxbuster_connector", "FeroxbusterConnector", "Feroxbuster",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.CONTENT_DISCOVERY,),
        ("endpoint", "path"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=1, default_enabled=False,
    ),

    # ------------------------------------------------------------------
    # Technology / TLS / cloud support
    # ------------------------------------------------------------------
    _c(
        "wappalyzer_connector", "WappalyzerConnector", "Wappalyzer",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.TECHNOLOGY_FINGERPRINT,),
        ("technology", "framework", "service"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
    ),
    _c(
        "whatweb_connector", "WhatWebConnector", "WhatWeb",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.TECHNOLOGY_FINGERPRINT,),
        ("technology", "framework", "service"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        manager_default_registered=False,
    ),
    _c(
        "sslyze_connector", "SSLyzeConnector", "SSLyze",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.TLS_ANALYSIS,),
        ("tls_metadata", "certificate_metadata"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
    ),
    _c(
        "testssl_connector", "TestSSLConnector", "testssl",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.TLS_ANALYSIS,),
        ("tls_metadata", "certificate_metadata"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
    ),
    _c(
        "cloudenum_connector", "CloudEnumConnector", "CloudEnum",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.CLOUD_DISCOVERY,),
        ("cloud_asset", "public_cloud_url"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
    ),
    _c(
        "s3scanner_connector", "S3ScannerConnector", "S3Scanner",
        (OsintTargetType.DOMAIN,),
        (DiscoveryGoal.CLOUD_DISCOVERY,),
        ("cloud_asset", "bucket"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
    ),

    # ------------------------------------------------------------------
    # Public-code / secret discovery
    # ------------------------------------------------------------------
    _c(
        "gitdorker_connector", "GitDorkerConnector", "GitDorker",
        (OsintTargetType.USERNAME, OsintTargetType.EMAIL, OsintTargetType.DOMAIN),
        (DiscoveryGoal.OPEN_WEB_DISCOVERY, DiscoveryGoal.SECRET_DISCOVERY),
        ("github_result", "public_url", "identifier"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
        requires_account=True,
        notes="Treat as credentialed GitHub search unless runtime proves a keyless mode.",
    ),
    _c(
        "trufflehog_connector", "TruffleHogConnector", "TruffleHog",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.SECRET_DISCOVERY,),
        ("secret_finding", "public_url"),
        ConnectorDisposition.SEPARATE, NetworkMode.MIXED,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        notes="Security/secret scanning belongs to a separate explicit workflow.",
    ),
    _c(
        "secretfinder_connector", "SecretFinderConnector", "SecretFinder",
        (OsintTargetType.URL,),
        (DiscoveryGoal.SECRET_DISCOVERY,),
        ("secret_finding", "endpoint"),
        ConnectorDisposition.SEPARATE, NetworkMode.ACTIVE,
        creates_new_entities=True, recursive_value=1, default_enabled=False,
    ),
    _c(
        "gitleaks_connector", "GitleaksConnector", "Gitleaks",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.SECRET_DISCOVERY,),
        ("secret_finding",),
        ConnectorDisposition.SEPARATE, NetworkMode.MIXED,
        creates_new_entities=False, recursive_value=0, default_enabled=False,
    ),

    # ------------------------------------------------------------------
    # Threat intelligence / reputation
    # ------------------------------------------------------------------
    _c(
        "abuseipdb_connector", "AbuseIPDBConnector", "AbuseIPDB",
        (OsintTargetType.IP,),
        (DiscoveryGoal.THREAT_INTELLIGENCE,),
        ("ip_reputation", "abuse_signal"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "alienvault_otx_connector", "AlienVaultOTXConnector", "AlienVault OTX",
        (OsintTargetType.IP, OsintTargetType.DOMAIN, OsintTargetType.URL, OsintTargetType.HASH),
        (DiscoveryGoal.THREAT_INTELLIGENCE,),
        ("indicator", "related_indicator", "reputation"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "greynoise_connector", "GreyNoiseConnector", "GreyNoise",
        (OsintTargetType.IP,),
        (DiscoveryGoal.THREAT_INTELLIGENCE,),
        ("ip_reputation", "internet_scanner_signal"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=1, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "haveibeenpwned_connector", "HaveIBeenPwnedConnector", "Have I Been Pwned",
        (OsintTargetType.EMAIL,),
        (DiscoveryGoal.THREAT_INTELLIGENCE,),
        ("breach_presence", "breach_metadata"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=False, recursive_value=2, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "hybrid_analysis_connector", "HybridAnalysisConnector", "Hybrid Analysis",
        (OsintTargetType.FILE, OsintTargetType.HASH, OsintTargetType.URL),
        (DiscoveryGoal.FILE_REPUTATION, DiscoveryGoal.THREAT_INTELLIGENCE),
        ("malware_report", "indicator", "reputation"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=2, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "intelligencex_connector", "IntelligenceXConnector", "Intelligence X",
        (
            OsintTargetType.USERNAME, OsintTargetType.EMAIL, OsintTargetType.DOMAIN,
            OsintTargetType.URL, OsintTargetType.IP, OsintTargetType.HASH,
        ),
        (DiscoveryGoal.OPEN_WEB_DISCOVERY, DiscoveryGoal.THREAT_INTELLIGENCE),
        ("indexed_record", "public_url", "related_identifier"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=5, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "urlscan_connector", "URLScanConnector", "urlscan.io",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.THREAT_INTELLIGENCE, DiscoveryGoal.WEB_METADATA),
        ("scan_record", "public_url", "domain", "ip"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=False,
        requires_api_key=True,
    ),
    _c(
        "virustotal_connector", "VirusTotalConnector", "VirusTotal",
        (OsintTargetType.DOMAIN, OsintTargetType.URL, OsintTargetType.IP, OsintTargetType.HASH),
        (DiscoveryGoal.THREAT_INTELLIGENCE, DiscoveryGoal.FILE_REPUTATION),
        ("reputation", "related_indicator", "relationship"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=3, default_enabled=False,
        requires_api_key=True,
    ),

    # ------------------------------------------------------------------
    # Keyless network metadata
    # ------------------------------------------------------------------
    _c(
        "asnlookup_connector", "ASNLookupConnector", "ASNLookup",
        (OsintTargetType.DOMAIN, OsintTargetType.IP),
        (DiscoveryGoal.NETWORK_ENRICHMENT,),
        ("asn", "network_prefix", "organization"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
    ),
    _c(
        "bgpview_connector", "BGPViewConnector", "BGPView",
        (OsintTargetType.IP,),
        (DiscoveryGoal.NETWORK_ENRICHMENT,),
        ("asn", "network_prefix", "organization"),
        ConnectorDisposition.SUPPORT, NetworkMode.PASSIVE_REMOTE,
        creates_new_entities=True, recursive_value=2, default_enabled=True,
    ),

    # ------------------------------------------------------------------
    # Automated aggregator
    # ------------------------------------------------------------------
    _c(
        "spiderfoot_connector", "SpiderFootConnector", "SpiderFoot",
        (
            OsintTargetType.USERNAME, OsintTargetType.EMAIL,
            OsintTargetType.DOMAIN, OsintTargetType.IP,
        ),
        (DiscoveryGoal.AUTOMATED_OSINT,),
        ("mixed_osint_finding", "related_identifier", "public_url"),
        ConnectorDisposition.CONDITIONAL, NetworkMode.MIXED,
        creates_new_entities=True, recursive_value=4, default_enabled=False,
        notes="Use only through an explicit module allow-list; do not run all modules automatically.",
    ),

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------
    _c(
        "aquatone_connector", "AquatoneConnector", "Aquatone",
        (OsintTargetType.DOMAIN, OsintTargetType.URL),
        (DiscoveryGoal.VISUALIZATION,),
        ("screenshot", "web_asset_visual"),
        ConnectorDisposition.SUPPORT, NetworkMode.ACTIVE,
        creates_new_entities=False, recursive_value=0, default_enabled=False,
    ),
)


OSINT_CAPABILITY_CATALOG: Mapping[str, OsintConnectorCapability] = MappingProxyType(
    {item.module: item for item in _CAPABILITIES}
)


def get_capability(module: str) -> OsintConnectorCapability | None:
    """Return capability metadata by connector module stem."""
    return OSINT_CAPABILITY_CATALOG.get(module)


def capabilities_for_target(
    target_type: OsintTargetType,
    *,
    default_only: bool = False,
) -> tuple[OsintConnectorCapability, ...]:
    """Return catalog entries that accept the target type."""
    items = [
        item
        for item in OSINT_CAPABILITY_CATALOG.values()
        if target_type in item.input_types
        and (not default_only or item.default_enabled)
    ]
    return tuple(
        sorted(
            items,
            key=lambda item: (
                -item.recursive_value,
                item.display_name.casefold(),
            ),
        )
    )


def capabilities_for_goal(
    goal: DiscoveryGoal,
    *,
    default_only: bool = False,
) -> tuple[OsintConnectorCapability, ...]:
    """Return catalog entries assigned to a discovery goal."""
    items = [
        item
        for item in OSINT_CAPABILITY_CATALOG.values()
        if goal in item.goals
        and (not default_only or item.default_enabled)
    ]
    return tuple(
        sorted(
            items,
            key=lambda item: (
                -item.recursive_value,
                item.display_name.casefold(),
            ),
        )
    )
