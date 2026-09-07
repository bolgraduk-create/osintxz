"""
OSINT manager.

Coordinates every OSINT connector.

Responsibilities:

- register connectors
- provide registry access

Does NOT:

- execute business logic
- access database
- call AI
"""

from __future__ import annotations

from app.osint.registry import ConnectorRegistry

from app.osint.connectors import (

    # Identity / Social

    SherlockConnector,
    MaigretConnector,
    HoleheConnector,
    LocalPhoneConnector,
    PhoneInfogaConnector,
    GHuntConnector,
    SocialScanConnector,


    # Domain / Network

    TheHarvesterConnector,
    AmassConnector,
    SubfinderConnector,
    DNSXConnector,
    CrtShConnector,


    # Web Discovery

    HTTPXConnector,
    NaabuConnector,
    NmapConnector,
    NucleiConnector,
    FFUFConnector,
    FeroxbusterConnector,
    KatanaConnector,
    HakrawlerConnector,


    # Historical

    WaybackurlsConnector,
    GauConnector,
    CommonCrawlConnector,
    ArchiveTodayConnector,


    # Technology

    WappalyzerConnector,


    # Secrets

    TruffleHogConnector,
    SecretFinderConnector,
    GitDorkerConnector,
    GitleaksConnector,
    SubjsConnector,


    # Threat Intelligence

    AbuseIPDBConnector,
    AlienVaultOTXConnector,
    ASNLookupConnector,
    BGPViewConnector,
    GreyNoiseConnector,
    HaveIBeenPwnedConnector,
    HybridAnalysisConnector,
    IntelligenceXConnector,
    URLScanConnector,
    VirusTotalConnector,


    # Cloud

    CloudEnumConnector,
    S3ScannerConnector,


    # SSL

    SSLyzeConnector,
    TestSSLConnector,


    # Automation

    SpiderFootConnector,


    # Visualization

    AquatoneConnector,

)


class OsintManager:
    """
    Central OSINT manager.
    """

    def __init__(
        self,
    ) -> None:

        self.registry = ConnectorRegistry()

        self._register_default_connectors()


    def _register_default_connectors(
        self,
    ) -> None:
        """
        Register built-in connectors.
        """

        connectors = [


            # ==================================================
            # Block A
            # Identity / Social OSINT
            # ==================================================

            SherlockConnector(),
            MaigretConnector(),
            HoleheConnector(),
            LocalPhoneConnector(),
            PhoneInfogaConnector(),
            GHuntConnector(),
            SocialScanConnector(),



            # ==================================================
            # Block B
            # Domain / Network Discovery
            # ==================================================

            TheHarvesterConnector(),
            AmassConnector(),
            SubfinderConnector(),
            DNSXConnector(),
            CrtShConnector(),



            # ==================================================
            # Block C
            # Web Discovery / Scanning
            # ==================================================

            HTTPXConnector(),
            NaabuConnector(),
            NmapConnector(),
            NucleiConnector(),
            FFUFConnector(),
            FeroxbusterConnector(),
            KatanaConnector(),
            HakrawlerConnector(),



            # ==================================================
            # Block D
            # Historical / URL Intelligence
            # ==================================================

            WaybackurlsConnector(),
            GauConnector(),
            CommonCrawlConnector(),
            ArchiveTodayConnector(),



            # ==================================================
            # Block E
            # Technology Analysis
            # ==================================================

            WappalyzerConnector(),



            # ==================================================
            # Block F
            # Secrets / Leaks
            # ==================================================

            TruffleHogConnector(),
            SecretFinderConnector(),
            GitDorkerConnector(),
            GitleaksConnector(),
            SubjsConnector(),



            # ==================================================
            # Block G
            # Threat Intelligence
            # ==================================================

            AbuseIPDBConnector(),
            AlienVaultOTXConnector(),
            ASNLookupConnector(),
            BGPViewConnector(),
            GreyNoiseConnector(),
            HaveIBeenPwnedConnector(),
            HybridAnalysisConnector(),
            IntelligenceXConnector(),
            URLScanConnector(),
            VirusTotalConnector(),



            # ==================================================
            # Block H
            # Cloud
            # ==================================================

            CloudEnumConnector(),
            S3ScannerConnector(),



            # ==================================================
            # Block I
            # SSL / TLS
            # ==================================================

            SSLyzeConnector(),
            TestSSLConnector(),



            # ==================================================
            # Block J
            # Automated OSINT
            # ==================================================

            SpiderFootConnector(),



            # ==================================================
            # Block K
            # Visualization
            # ==================================================

            AquatoneConnector(),

        ]


        for connector in connectors:

            self.registry.register(
                connector,
            )