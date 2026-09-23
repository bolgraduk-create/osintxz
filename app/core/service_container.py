"""
Application Service Container.

Responsible for:

- creating all domain services
- creating application services
- creating AI layer
- creating OSINT layer
- creating controllers
- dependency injection

This is the single Composition Root
for the entire application.
"""

from __future__ import annotations

from app.application.investigation_target_enrichment_service import (
    InvestigationTargetEnrichmentService,
)

from app.application.registry_intelligence_service import RegistryIntelligenceService
from app.intelligence_sources.adapters.ares import CzechAresAdapter
from app.intelligence_sources.adapters.brreg import NorwayBrregAdapter
from app.intelligence_sources.adapters.crossref import CrossrefAdapter
from app.intelligence_sources.adapters.openalex import OpenAlexAdapter
from app.intelligence_sources.adapters.csl import TradeCslAdapter
from app.intelligence_sources.adapters.sam_gov import SamGovEntityAdapter
from app.intelligence_sources.adapters.sec_edgar import SecEdgarAdapter
from app.intelligence_sources.adapters.ted import TedSearchAdapter
from app.intelligence_sources.adapters.australia_abn import AustraliaAbnLookupAdapter
from app.intelligence_sources.adapters.canada_corporations import CanadaFederalCorporationsAdapter
from app.intelligence_sources.adapters.charity_uk import UkCharityCommissionAdapter
from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter
from app.intelligence_sources.adapters.poland_regon import PolandRegonAdapter
from app.intelligence_sources.adapters.hibp_breach import HibpBreachAdapter
from app.intelligence_sources.adapters.intelligencex import (
    IntelligenceXMetadataAdapter,
    IntelligenceXSearchClient,
)
from app.intelligence_sources.adapters.tor_public import TorPublicOnionAdapter
from app.intelligence_sources.adapters.hibp_extended import (
    HibpExtendedClient,
    HibpPasteAdapter,
    HibpVerifiedDomainAdapter,
    HibpStealerLogEmailAdapter,
    HibpStealerLogEmailDomainAdapter,
    HibpStealerLogWebsiteDomainAdapter,
)
from app.intelligence_sources.adapters.github_secret_scanning import (
    GitHubSecretScanningAdapter,
    GitHubSecretScanningClient,
)
from app.darkweb_intelligence.ahmia import AhmiaDirectoryClient
from app.darkweb_intelligence.discovery import DarkWebDiscoveryService
from app.intelligence_sources.adapters.onion_discovery import TorOnionDiscoveryAdapter
from app.intelligence_sources.adapters.wikidata_search import WikidataEntitySearchAdapter
from app.intelligence_sources.adapters.orcid_public import OrcidPublicAdapter
from app.intelligence_sources.adapters.nvd_cve import NvdCveAdapter
from app.intelligence_sources.adapters.openfda import OpenFdaAdapter
from app.intelligence_sources.adapters.fec import OpenFecAdapter
from app.intelligence_sources.adapters.icij_offshore import IcijOffshoreLeaksAdapter
from app.intelligence_sources.adapters.nppes_npi import NppesNpiAdapter
from app.intelligence_sources.adapters.github_public import GitHubPublicUserAdapter
from app.intelligence_sources.adapters.gitlab_public import GitLabPublicUserAdapter
from app.intelligence_sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.intelligence_sources.adapters.europe_pmc import EuropePmcAdapter
from app.intelligence_sources.adapters.library_of_congress import LibraryOfCongressAdapter
from app.intelligence_sources.adapters.fbi_wanted import FbiWantedAdapter
from app.intelligence_sources.adapters.first_epss import FirstEpssAdapter
from app.intelligence_sources.adapters.circl_hashlookup import CirclHashlookupAdapter
from app.intelligence_sources.adapters.shodan_internetdb import ShodanInternetDbAdapter
from app.intelligence_sources.adapters.cisa_kev import CisaKevAdapter
from app.intelligence_sources.adapters.rdap_bootstrap import RdapBootstrapAdapter
from app.intelligence_sources.adapters.ripestat import RipeStatAdapter
from app.intelligence_sources.adapters.peeringdb import PeeringDbAdapter
from app.intelligence_sources.adapters.google_dns import GooglePublicDnsAdapter
from app.intelligence_sources.adapters.usaspending import UsaSpendingRecipientAdapter
from app.intelligence_sources.adapters.federal_register import FederalRegisterAdapter
from app.intelligence_sources.adapters.datacite import DataCiteAdapter
from app.intelligence_sources.adapters.zenodo_public import ZenodoPublicAdapter
from app.intelligence_sources.adapters.internet_archive import InternetArchiveMetadataAdapter
from app.intelligence_sources.adapters.un_sanctions import UnSecurityCouncilSanctionsAdapter
from app.exposure_intelligence.service import ExposureFederationService
from app.exposure_intelligence.persistence import ExposurePersistenceService
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.ror import RorAdapter
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService
from app.application.registry_persistence_service import RegistryPersistenceService
from app.core.config import settings
from app.breach_intelligence.catalog import register_hibp_sources
from app.darkweb_intelligence.catalog import register_darkweb_sources
from app.darkweb_intelligence.service import DarkWebIntelligenceService
from app.darkweb_intelligence.tor_client import TorOnionHttpClient
from app.breach_intelligence.hibp_client import HibpHttpClient
from app.breach_intelligence.service import BreachIntelligenceService
from app.intelligence_sources.catalog import IntelligenceSourceCatalog
from app.intelligence_sources.builtin_sources import register_massive_remote_sources
from app.intelligence_sources.policy import IntelligenceDataSanitizer
from app.infrastructure.registries.gleif_client import GleifRegistryHttpClient
from app.infrastructure.registries.vies_client import ViesRegistryHttpClient
from app.infrastructure.registries.opencorporates_client import OpenCorporatesHttpClient
from app.infrastructure.registries.courtlistener_client import CourtListenerHttpClient
from app.infrastructure.registries.recap_client import (
    CourtListenerRecapHttpClient,
    PacerPaidFetchGuard,
)
from app.infrastructure.registries.companies_house_client import CompaniesHouseHttpClient
from app.infrastructure.registries.poland_krs_client import PolandKrsHttpClient
from app.infrastructure.registries.registry_api_client import RegistryApiHttpClient
from app.registry_intelligence.countries.ukraine import (
    UA_EDR_PROVIDER_INFO,
    UA_EDRSR_PROVIDER_INFO,
)
from app.registry_intelligence.providers.gleif import GleifRegistryProvider
from app.registry_intelligence.providers.vies import ViesRegistryProvider
from app.registry_intelligence.providers.opencorporates import OpenCorporatesRegistryProvider
from app.registry_intelligence.providers.courtlistener import CourtListenerRegistryProvider
from app.registry_intelligence.providers.recap import (
    CourtListenerRecapRegistryProvider,
)
from app.registry_intelligence.providers.companies_house import CompaniesHouseRegistryProvider
from app.registry_intelligence.providers.poland_krs import PolandKrsRegistryProvider
from app.registry_intelligence.providers.remote import RemoteRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry

from sqlalchemy.orm import Session

# ==========================================================
# AI
# ==========================================================

from app.core.ai_factory import (
    create_ai_stack,
)

# ==========================================================
# Domain Services
# ==========================================================

from app.services.case_service import (
    CaseService,
)

from app.services.source_service import (
    SourceService,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.evidence.source_reliability import (
    SourceReliabilityScoringService,
)

from app.evidence.evidence_strength import (
    EvidenceStrengthScoringService,
)

from app.evidence.corroboration import (
    EvidenceCorroborationService,
)

from app.evidence.contradiction_detection import (
    EvidenceContradictionDetectionService,
)

from app.evidence.source_independence import (
    EvidenceSourceIndependenceService,
)

from app.evidence.evidence_confidence import (
    EvidenceConfidenceAggregationService,
)

from app.evidence.evidence_confidence_explanation import (
    EvidenceConfidenceExplanationService,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.timeline_service import (
    TimelineService,
)

from app.services.report_service import (
    ReportService,
)

from app.services.message_service import (
    MessageService,
)

from app.services.document_service import (
    DocumentService,
)

from app.services.artifact_service import (
    ArtifactService,
)

from app.services.entity_graph_service import (
    EntityGraphService,
)

from app.analysis.unified_graph_analysis import (
    UnifiedGraphAnalysisService,
)

from app.analysis.graph_explainability import (
    GraphExplainabilityService,
)

from app.analysis.unified_temporal_analysis import (
    UnifiedTemporalAnalysisService,
)

from app.analysis.unified_anomaly_analysis import (
    UnifiedAnomalyAnalysisService,
)

from app.services.file_import_service import (
    FileImportService,
)

from app.services.image_analysis_service import (
    ImageAnalysisService,
)

from app.controllers.file_import_controller import (
    FileImportController,
)

from app.processing.file_processing_router import (
    FileProcessingRouter,
)

from app.services.image_comparison_service import (
    ImageComparisonService,
)

from app.services.image_similarity_search_service import (
    ImageSimilaritySearchService,
)

from app.repositories.search_index_repository import (
    SearchIndexRepository,
)

from app.repositories.search_embedding_repository import (
    SearchEmbeddingRepository,
)

from app.services.search_index_builder import (
    SearchIndexBuilder,
)

from app.services.lexical_search_retriever import (
    LexicalSearchRetriever,
)

from app.services.structured_search_retriever import (
    StructuredSearchRetriever,
)

from app.services.fuzzy_search_service import (
    FuzzySearchService,
)

from app.services.fuzzy_search_retriever import (
    FuzzySearchRetriever,
)

from app.services.ollama_embedding_service import (
    OllamaEmbeddingService,
)

from app.services.search_embedding_indexer import (
    SearchEmbeddingIndexer,
)

from app.services.semantic_search_retriever import (
    SemanticSearchRetriever,
)

from app.services.unified_search_service import (
    UnifiedSearchService,
)

from app.services.search_confidence_service import (
    SearchConfidenceService,
)

from app.services.search_explanation_service import (
    SearchExplanationService,
)

from app.services.investigation_rag_retrieval_service import (
    InvestigationRAGRetrievalService,
)

from app.services.investigation_evidence_confidence_search_enrichment_service import (
    InvestigationEvidenceConfidenceSearchEnrichmentService,
)

from app.services.investigation_rag_context_builder import (
    InvestigationRAGContextBuilder,
)

from app.services.investigation_rag_prompt_service import (
    InvestigationRAGPromptService,
)

from app.services.investigation_rag_summary_service import (
    InvestigationRAGSummaryService,
)

from app.services.investigation_rag_conclusions_service import (
    InvestigationRAGConclusionsService,
)

from app.services.investigation_rag_grounded_citation_service import (
    InvestigationRAGGroundedCitationService,
)

from app.application.analysis_chat_service import (
    AnalysisChatService,
)

from app.services.investigation_unified_analytical_context_service import (
    InvestigationUnifiedAnalyticalContextService,
)

from app.repositories.face_profile_repository import (
    FaceProfileRepository,
)

from app.repositories.face_embedding_repository import (
    FaceEmbeddingRepository,
)

from app.services.face_memory_service import (
    FaceMemoryService,
)

from app.services.face_analysis_service import (
    FaceAnalysisService,
)

from app.services.image_gps_location_service import (
    ImageGpsLocationService,
)

from app.services.evidence_link_service import (
    EvidenceLinkService,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)

from app.repositories.search_semantic_chunk_repository import (
    SearchSemanticChunkRepository,
)

from app.repositories.search_semantic_chunk_embedding_repository import (
    SearchSemanticChunkEmbeddingRepository,
)

from app.services.search_semantic_chunk_embedding_indexer import (
    SearchSemanticChunkEmbeddingIndexer,
)

from app.services.composite_semantic_retriever import (
    CompositeSemanticRetriever,
)

# ==========================================================
# Import Pipeline
# ==========================================================

from app.collectors.telegram.telegram_collector import (
    TelegramCollector,
)

from app.services.collection_service import (
    CollectionService,
)

from app.services.unified_extraction_service import (
    UnifiedExtractionService,
)

from app.services.entity_resolution_pipeline import (
    EntityResolutionPipeline,
)

from app.services.telegram_entity_mapper_service import (
    TelegramEntityMapperService,
)

from app.services.telegram_entity_import_service import (
    TelegramEntityImportService,
)

from app.services.telegram_interaction_service import (
    TelegramInteractionService,
)

from app.services.telegram_relationship_import_service import (
    TelegramRelationshipImportService,
)

from app.services.telegram_timeline_mapper_service import (
    TelegramTimelineMapperService,
)

from app.services.telegram_timeline_import_service import (
    TelegramTimelineImportService,
)

from app.services.investigation_summary_builder import (
    InvestigationSummaryBuilder,
)

from app.services.telegram_report_import_service import (
    TelegramReportImportService,
)

from app.services.telegram_import_service import (
    TelegramImportService,
)

from app.application.investigation_ai_service import (
    InvestigationAIService,
)

from app.ai.providers.ai_investigation_service import (
    AIInvestigationService as AIExecutionService,
)

from app.services.message_semantic_chunk_builder import (
    MessageSemanticChunkBuilder,
)

from app.services.message_semantic_chunk_service import (
    MessageSemanticChunkService,
)

from app.services.semantic_chunk_retriever import (
    SemanticChunkRetriever,
)

# ==========================================================
# OSINT
# ==========================================================

from app.osint.manager import (
    OsintManager,
)

from app.osint.pipeline import (
    OsintPipeline,
)

from app.osint.enrichment_execution import (
    OsintEnrichmentExecutionService,
)

from app.osint.pivot_router import OsintCapabilityRouter
from app.osint.credential_policy import (
    configured_threat_intelligence_modules,
)

from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)

from app.osint.target_builder import (
    OsintTargetBuilder,
)

# ==========================================================
# Application Services
# ==========================================================

from app.application.workflow import (
    InvestigationWorkflow,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)

from app.application.investigation_graph_analysis_service import (
    InvestigationGraphAnalysisService,
)

from app.application.investigation_temporal_analysis_service import (
    InvestigationTemporalAnalysisService,
)

from app.application.investigation_entity_feature_extraction_service import (
    InvestigationEntityFeatureExtractionService,
)

from app.application.investigation_anomaly_analysis_service import (
    InvestigationAnomalyAnalysisService,
)

from app.application.investigation_entity_clustering_service import (
    InvestigationEntityClusteringService,
)

from app.application.investigation_entity_resolution_analysis_service import (
    InvestigationEntityResolutionAnalysisService,
)

from app.application.investigation_evidence_analysis_service import (
    InvestigationEvidenceAnalysisService,
)

from app.application.investigation_evidence_confidence_service import (
    InvestigationEvidenceConfidenceService,
)

from app.application.investigation_multimodal_analysis_service import (
    InvestigationMultimodalAnalysisService,
)

from app.analysis.multimodal_image_aggregation import (
    MultimodalImageAggregationService,
)

from app.application.investigation_analysis_orchestrator import (
    InvestigationAnalysisOrchestrator,
)

from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)

from app.application.ai_workspace_service import (
    AIWorkspaceService,
)

from app.application.import_workspace_service import (
    ImportWorkspaceService,
)

from app.application.osint_workspace_service import (
    OsintWorkspaceService,
)

from app.application.osint_enrichment_service import (
    OsintEnrichmentService,
)

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
)

from app.application.workspaces import (
    ApplicationWorkspaces,
)

from app.application.services import (
    InvestigationApplicationService,
)

# ==========================================================
# Controllers
# ==========================================================

from app.controllers.case_controller import (
    CaseController,
)

from app.controllers.workspace_controller import (
    WorkspaceController,
)

from app.controllers.ai_analysis_controller import (
    AIAnalysisController,
)

from app.controllers.import_controller import (
    ImportController,
)

from app.controllers.osint_controller import (
    OsintController,
)

from app.localization import (
    TranslationManager,
    configure_translator,
)



from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentService,
)
from app.osint.open_web.extraction_bridge import (
    OpenWebIdentifierExtractionBridge,
)
from app.osint.open_web.registry import (
    OpenWebProviderRegistry,
)
from app.osint.open_web.service import (
    OpenWebDiscoveryService,
)


from app.infrastructure.open_web.common_crawl_client import (
    CommonCrawlHttpClient,
)
from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)
from app.osint.open_web.providers.gdelt_phone_exact import (
    GdeltPhoneExactOpenWebProvider,
)
from app.osint.open_web.providers.searxng_phone_exact import (
    SearxngPhoneExactOpenWebProvider,
)
from app.osint.open_web.providers.targeted_phone_public_sources import (
    TargetedPhonePublicSourcesProvider,
)
from app.osint.open_web.providers.live_web import (
    LiveWebOpenWebProvider,
)

from app.infrastructure.open_web.common_crawl_warc_client import (
    CommonCrawlWarcContentClient,
)
from app.osint.open_web.content_hydration import (
    CommonCrawlContentHydrator,
)


from app.infrastructure.open_web.common_crawl_metadata_client import (
    CommonCrawlMetadataClient,
)
from app.infrastructure.open_web.common_crawl_raw_index import (
    CommonCrawlRawIndexClient,
)

from app.application.open_web_recursive_pivot_service import (
    OpenWebRecursivePivotService,
)

class ServiceContainer:
    """
    Central dependency injection container.

    This is the only Composition Root
    of the application.
    """

    def __init__(
        self,
        session: Session,
        *,
        ai_provider_name: str | None = None,
        ai_model_name: str | None = None,
        ai_reasoning_effort: str | None = None,
    ) -> None:

        self.session = session

        # ==================================================
        # Localization
        # ==================================================

        self.translation_manager = (
            TranslationManager()
        )

        configure_translator(
            self.translation_manager
        )

        # ==================================================
        # AI
        # ==================================================

        (
            self.ai_manager,
            self.ai_analyzer,
        ) = create_ai_stack(
            provider_name=ai_provider_name,
            model_name=ai_model_name,
            reasoning_effort=ai_reasoning_effort,
        )

        # ==================================================
        # Core Domain Services
        # ==================================================

        self.case_service = CaseService(
            session
        )

        self.source_service = SourceService(
            session
        )

        # ==================================================
        # Unified Search
        # ==================================================

        # --------------------------------------------------
        # Search persistence
        # --------------------------------------------------

        self.search_index_repository = (
            SearchIndexRepository(
                session
            )
        )

        self.search_embedding_repository = (
            SearchEmbeddingRepository(
                session
            )
        )

        self.search_semantic_chunk_repository = (
            SearchSemanticChunkRepository(
                self.session
            )
        )

        self.search_semantic_chunk_embedding_repository = (
            SearchSemanticChunkEmbeddingRepository(
                self.session
            )
        )

        self.message_semantic_chunk_builder = (
            MessageSemanticChunkBuilder()
        )


        # --------------------------------------------------
        # Search index construction
        # --------------------------------------------------

        self.search_index_builder = (
            SearchIndexBuilder(
                session=session,
                repository=(
                    self.search_index_repository
                ),
            )
        )

        self.message_semantic_chunk_builder = (
            MessageSemanticChunkBuilder()
        )

        # --------------------------------------------------
        # Embedding provider
        # --------------------------------------------------

        self.embedding_service = (
            OllamaEmbeddingService()
        )

        self.search_embedding_indexer = (
            SearchEmbeddingIndexer(
                search_index_repository=(
                    self.search_index_repository
                ),
                search_embedding_repository=(
                    self.search_embedding_repository
                ),
                embedding_service=(
                    self.embedding_service
                ),
            )
        )

        self.search_indexing_service = (
            SearchIndexingService(
                search_index_builder=(
                    self.search_index_builder
                ),
                search_index_repository=(
                    self.search_index_repository
                ),
                search_embedding_repository=(
                    self.search_embedding_repository
                ),
                search_embedding_indexer=(
                    self.search_embedding_indexer
                ),
            )
        )

        self.search_semantic_chunk_embedding_indexer = (
            SearchSemanticChunkEmbeddingIndexer(
                chunk_repository=(
                    self.search_semantic_chunk_repository
                ),
                embedding_repository=(
                    self.search_semantic_chunk_embedding_repository
                ),
                embedding_service=(
                    self.embedding_service
                ),
            )
        )

        # --------------------------------------------------
        # Lexical / BM25
        # --------------------------------------------------

        self.lexical_search_retriever = (
            LexicalSearchRetriever(
                repository=(
                    self.search_index_repository
                ),
            )
        )

        # --------------------------------------------------
        # Fuzzy
        # --------------------------------------------------

        self.fuzzy_search_service = (
            FuzzySearchService()
        )

        self.fuzzy_search_retriever = (
            FuzzySearchRetriever(
                repository=(
                    self.search_index_repository
                ),
                fuzzy_search_service=(
                    self.fuzzy_search_service
                ),
            )
        )

        # --------------------------------------------------
        # Semantic / pgvector
        # --------------------------------------------------

        self.semantic_search_retriever = (
            SemanticSearchRetriever(
                repository=(
                    self.search_embedding_repository
                ),
                embedding_service=(
                    self.embedding_service
                ),
            )
        )




        # ==================================================
        # Search-aware Domain Services
        # ==================================================

        self.evidence_service = EvidenceService(
            session,
            search_indexing_service=(
                self.search_indexing_service
            ),
        )

        self.evidence_link_service = (
            EvidenceLinkService(
                session
            )
        )

        # ==================================================
        # Image Services
        # ==================================================

        self.image_analysis_service = (
            ImageAnalysisService(
                evidence_service=(
                    self.evidence_service
                ),
            )
        )

        self.image_comparison_service = (
            ImageComparisonService(
                evidence_service=(
                    self.evidence_service
                ),
                image_analysis_service=(
                    self.image_analysis_service
                ),
            )
        )

        self.image_similarity_search_service = (
            ImageSimilaritySearchService(
                evidence_service=(
                    self.evidence_service
                ),
                image_comparison_service=(
                    self.image_comparison_service
                ),
            )
        )

        self.face_profile_repository = (
            FaceProfileRepository(
                session
            )
        )

        self.face_embedding_repository = (
            FaceEmbeddingRepository(
                session
            )
        )

        self.face_memory_service = (
            FaceMemoryService(
                profile_repository=(
                    self.face_profile_repository
                ),
                embedding_repository=(
                    self.face_embedding_repository
                ),
            )
        )

        self.face_analysis_service = (
            FaceAnalysisService(
                image_analysis_service=(
                    self.image_analysis_service
                ),
                face_memory_service=(
                    self.face_memory_service
                ),
            )
        )

        self.entity_service = EntityService(
            session
        )

        self.unified_extraction_service = (
            UnifiedExtractionService(
                session=session,
                entity_service=(
                    self.entity_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                evidence_link_service=(
                    self.evidence_link_service
                ),
            )
        )

        self.relationship_service = (
            RelationshipService(
                session
            )
        )

        self.entity_graph_service = (
            EntityGraphService(
                session
            )
        )

        self.timeline_service = TimelineService(
            session
        )

        self.report_service = ReportService(
            session
        )

        self.message_service = MessageService(
            session,
            search_indexing_service=(
                self.search_indexing_service
            ),
        )

        self.message_semantic_chunk_service = (
            MessageSemanticChunkService(
                message_repository=(
                    self.message_service.repository
                ),
                chunk_repository=(
                    self.search_semantic_chunk_repository
                ),
                chunk_builder=(
                    self.message_semantic_chunk_builder
                ),
            )
        )

        self.document_service = DocumentService(
            session,
            search_indexing_service=(
                self.search_indexing_service
            ),
        )

        self.artifact_service = ArtifactService(
            session,
            search_indexing_service=(
                self.search_indexing_service
            ),
        )

        self.file_processing_router = (
            FileProcessingRouter()
        )

        self.semantic_chunk_retriever = (
            SemanticChunkRetriever(
                repository=(
                    self.search_semantic_chunk_embedding_repository
                ),
                message_repository=(
                    self.message_service.repository
                ),
                embedding_service=(
                    self.embedding_service
                ),
            )
        )

        # --------------------------------------------------
        # Structured Entity / Evidence retrieval
        # --------------------------------------------------

        self.structured_search_retriever = (
            StructuredSearchRetriever(
                entity_repository=(
                    self.entity_service.repository
                ),
                evidence_repository=(
                    self.evidence_service.repository
                ),
            )
        )

        # --------------------------------------------------
        # Composite Semantic
        # --------------------------------------------------

        self.composite_semantic_retriever = (
            CompositeSemanticRetriever(
                embedding_service=(
                    self.embedding_service
                ),
                message_retriever=(
                    self.semantic_chunk_retriever
                ),
                object_retriever=(
                    self.semantic_search_retriever
                ),
            )
        )

        # --------------------------------------------------
        # Unified orchestration + RRF + explanations
        # --------------------------------------------------

        self.search_confidence_service = (
            SearchConfidenceService()
        )

        self.search_explanation_service = (
            SearchExplanationService()
        )

        self.unified_search_service = (
            UnifiedSearchService(
                retrievers=[
                    self.structured_search_retriever,
                    self.lexical_search_retriever,
                    self.fuzzy_search_retriever,
                    self.composite_semantic_retriever,
                ],
                search_confidence_service=(
                    self.search_confidence_service
                ),
                search_explanation_service=(
                    self.search_explanation_service
                ),
            )
        )

        # ==================================================
        # AI / RAG Retrieval
        # ==================================================

        self.investigation_evidence_confidence_search_enrichment_service = (
            InvestigationEvidenceConfidenceSearchEnrichmentService()
        )

        self.investigation_rag_retrieval_service = (
            InvestigationRAGRetrievalService(
                unified_search_service=(
                    self.unified_search_service
                ),
                evidence_confidence_enrichment_service=(
                    self.investigation_evidence_confidence_search_enrichment_service
                ),
            )
        )

        self.investigation_rag_context_builder = (
            InvestigationRAGContextBuilder()
        )

        # ==================================================
        # Collector
        # ==================================================

        self.telegram_collector = (
            TelegramCollector()
        )

        # ==================================================
        # Collection
        # ==================================================

        self.collection_service = (
            CollectionService(
                source_service=(
                    self.source_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                message_service=(
                    self.message_service
                ),
                document_service=(
                    self.document_service
                ),
                artifact_service=(
                    self.artifact_service
                ),
            )
        )



        self.file_import_service = (
            FileImportService(
                collection_service=(
                    self.collection_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                file_processing_router=(
                    self.file_processing_router
                ),
                search_indexing_service=(
                    self.search_indexing_service
                ),
            )
        )



        self.file_import_controller = (
            FileImportController(
                container=self,
                file_import_service=(
                    self.file_import_service
                ),
            )
        )

        # ==================================================
        # AI Workspace and validation
        # ==================================================

        self.ai_workspace_service = (
            AIWorkspaceService(
                case_service=(
                    self.case_service
                ),
            )
        )

        self.investigation_ai_service = (
            InvestigationAIService(
                workspace_service=(
                    self.ai_workspace_service
                ),
            )
        )

        # ==================================================
        # AI Investigation execution
        # ==================================================

        self.ai_execution_service = (
            AIExecutionService(
                session=session,
                ai_manager=(
                    self.ai_manager
                ),
            )
        )

        # ==================================================
        # AI / RAG Prompt Layer
        # ==================================================

        # Reuse the exact PromptManager instance already
        # owned by the existing AI execution service.
        self.prompt_manager = (
            self.ai_execution_service.prompt_manager
        )

        self.investigation_rag_prompt_service = (
            InvestigationRAGPromptService(
                prompt_manager=(
                    self.prompt_manager
                ),
            )
        )

        # ==================================================
        # AI / RAG Investigation Summary
        # ==================================================

        self.investigation_rag_summary_service = (
            InvestigationRAGSummaryService(
                retrieval_service=(
                    self.investigation_rag_retrieval_service
                ),
                context_builder=(
                    self.investigation_rag_context_builder
                ),
                prompt_service=(
                    self.investigation_rag_prompt_service
                ),
                ai_execution_service=(
                    self.ai_execution_service
                ),
            )
        )

        # ==================================================
        # AI / RAG Conclusions
        # ==================================================

        self.investigation_rag_conclusions_service = (
            InvestigationRAGConclusionsService(
                retrieval_service=(
                    self.investigation_rag_retrieval_service
                ),
                context_builder=(
                    self.investigation_rag_context_builder
                ),
                prompt_manager=(
                    self.prompt_manager
                ),
                ai_execution_service=(
                    self.ai_execution_service
                ),
            )
        )

        # ==================================================
        # AI / RAG Grounded Evidence Citations
        # ==================================================

        self.investigation_rag_grounded_citation_service = (
            InvestigationRAGGroundedCitationService()
        )

        # ==================================================
        # Conversational Analysis Chat
        # ==================================================

        self.analysis_chat_service = (
            AnalysisChatService(
                retrieval_service=(
                    self.investigation_rag_retrieval_service
                ),
                context_builder=(
                    self.investigation_rag_context_builder
                ),
                ai_execution_service=(
                    self.ai_execution_service
                ),
                citation_service=(
                    self.investigation_rag_grounded_citation_service
                ),
                prompt_manager=(
                    self.prompt_manager
                ),
            )
        )

        # ==================================================
        # Unified Analytical Context
        # ==================================================

        self.investigation_unified_analytical_context_service = (
            InvestigationUnifiedAnalyticalContextService()
        )

        # ==================================================
        # Telegram Entity Import
        # ==================================================

        self.telegram_entity_mapper_service = (
            TelegramEntityMapperService()
        )

        self.telegram_entity_import_service = (
            TelegramEntityImportService(
                entity_service=(
                    self.entity_service
                ),
                mapper=(
                    self.telegram_entity_mapper_service
                ),
            )
        )


        # ==================================================
        # Telegram Relationship Import
        # ==================================================

        self.telegram_interaction_service = (
            TelegramInteractionService()
        )

        self.telegram_relationship_import_service = (
            TelegramRelationshipImportService(
                relationship_service=(
                    self.relationship_service
                ),
                interaction_service=(
                    self.telegram_interaction_service
                ),
                entity_service=(
                    self.entity_service
                ),
            )
        )

        # ==================================================
        # Telegram Timeline Import
        # ==================================================

        self.telegram_timeline_mapper_service = (
            TelegramTimelineMapperService()
        )

        self.telegram_timeline_import_service = (
            TelegramTimelineImportService(
                mapper=(
                    self.telegram_timeline_mapper_service
                ),
                timeline_service=(
                    self.timeline_service
                ),
                entity_service=(
                    self.entity_service
                ),
            )
        )

        # ==================================================
        # Investigation Summary
        # ==================================================

        self.investigation_summary_builder = (
            InvestigationSummaryBuilder(
                message_service=(
                    self.message_service
                ),
                entity_service=(
                    self.entity_service
                ),
                relationship_service=(
                    self.relationship_service
                ),
                timeline_service=(
                    self.timeline_service
                ),
            )
        )

        self.telegram_report_import_service = (
            TelegramReportImportService(
                summary_builder=(
                    self.investigation_summary_builder
                ),
                report_service=(
                    self.report_service
                ),
            )
        )

        # ==================================================
        # Telegram Import
        # ==================================================

        self.telegram_import_service = (
            TelegramImportService(
                collector=(
                    self.telegram_collector
                ),
                extraction_service=(
                    self.unified_extraction_service
                ),
                collection_service=(
                    self.collection_service
                ),
                source_service=(
                    self.source_service
                ),
                entity_import_service=(
                    self.telegram_entity_import_service
                ),
                relationship_import_service=(
                    self.telegram_relationship_import_service
                ),
                timeline_import_service=(
                    self.telegram_timeline_import_service
                ),
                report_import_service=(
                    self.telegram_report_import_service
                ),
                search_indexing_service=(
                    self.search_indexing_service
                ),
            )
        )

        # ==================================================
        # OSINT Infrastructure
        # ==================================================

        self.osint_manager = (
            OsintManager()
        )

        # M021.16.5.2C1 User Scanner runtime registration
        from app.osint.connectors.user_scanner_connector import (
            UserScannerConnector,
        )

        self.osint_manager.registry.register(
            UserScannerConnector()
        )

        # M021.16.5.1 Gravatar runtime registration
        from app.osint.connectors.gravatar_connector import (
            GravatarConnector,
        )

        self.osint_manager.registry.register(
            GravatarConnector()
        )

        self.osint_pipeline = (
            OsintPipeline(
                manager=(
                    self.osint_manager
                ),
            )
        )

        self.osint_target_builder = (
            OsintTargetBuilder()
        )

        self.osint_capability_router = (
            OsintCapabilityRouter(
                configured_credential_modules=(
                    configured_threat_intelligence_modules(settings)
                ),
            )
        )

        self.osint_enrichment_execution_service = (
            OsintEnrichmentExecutionService(
                pipeline=(
                    self.osint_pipeline
                ),
                router=(
                    self.osint_capability_router
                ),
            )
        )

        self.osint_finding_persistence_service = (
            OsintFindingPersistenceService(
                source_service=(
                    self.source_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                entity_service=(
                    self.entity_service
                ),
                evidence_link_service=(
                    self.evidence_link_service
                ),
            )
        )

        # ==================================================
        # R13.6 — Breach Intelligence / HIBP.
        self.intelligence_source_catalog = IntelligenceSourceCatalog()
        register_hibp_sources(self.intelligence_source_catalog)

        register_darkweb_sources(self.intelligence_source_catalog)
        self.remote_source_coverage = register_massive_remote_sources(
            self.intelligence_source_catalog
        )
        self.tor_onion_http_client = TorOnionHttpClient(
            proxy_url=settings.darkweb_tor_socks_proxy,
        )
        self.darkweb_intelligence_service = DarkWebIntelligenceService(
            client=self.tor_onion_http_client,
            data_sanitizer=IntelligenceDataSanitizer(),
        )

        self.hibp_http_client = HibpHttpClient(
            api_key=settings.haveibeenpwned_api_key
        )
        self.breach_intelligence_service = BreachIntelligenceService(
            hibp_client=self.hibp_http_client,
            data_sanitizer=IntelligenceDataSanitizer(),
        )

        # R13.12 — metadata-only Intelligence X search client.
        self.intelligencex_search_client = IntelligenceXSearchClient(
            api_key=settings.intelligencex_api_key,
            base_url=settings.intelligencex_api_url,
        )
        self.hibp_extended_client = HibpExtendedClient(
            api_key=settings.haveibeenpwned_api_key,
        )
        self.github_secret_scanning_client = GitHubSecretScanningClient(
            token=settings.github_secret_scanning_token,
        )

        # R13.14 — bounded public onion discovery + Ahmia safety metadata.
        self.ahmia_directory_client = AhmiaDirectoryClient()
        self.darkweb_discovery_service = DarkWebDiscoveryService(
            page_service=self.darkweb_intelligence_service,
            ahmia_client=self.ahmia_directory_client,
        )

        # R13.9 — Remote Adapter Pack 1.
        self.remote_source_adapter_registry = RemoteSourceAdapterRegistry()
        self.remote_source_adapter_registry.register(NorwayBrregAdapter())
        self.remote_source_adapter_registry.register(CzechAresAdapter())
        self.remote_source_adapter_registry.register(CrossrefAdapter())
        self.remote_source_adapter_registry.register(RorAdapter())
        self.remote_source_adapter_registry.register(
            OpenAlexAdapter(api_key=settings.openalex_api_key)
        )
        self.remote_source_adapter_registry.register(
            SecEdgarAdapter(user_agent=settings.sec_edgar_user_agent)
        )
        self.remote_source_adapter_registry.register(TedSearchAdapter())
        self.remote_source_adapter_registry.register(
            SamGovEntityAdapter(api_key=settings.sam_gov_api_key)
        )
        self.remote_source_adapter_registry.register(
            TradeCslAdapter(api_key=settings.trade_gov_api_key)
        )

        self.remote_source_adapter_registry.register(FranceEnterpriseSearchAdapter())
        self.remote_source_adapter_registry.register(
            AustraliaAbnLookupAdapter(authentication_guid=settings.abn_lookup_guid)
        )
        self.remote_source_adapter_registry.register(
            CanadaFederalCorporationsAdapter(api_key=settings.canada_corporations_api_key)
        )
        self.remote_source_adapter_registry.register(
            UkCharityCommissionAdapter(api_key=settings.uk_charity_commission_api_key)
        )
        self.remote_source_adapter_registry.register(
            PolandRegonAdapter(user_key=settings.poland_regon_api_key)
        )

        # R13.12 — Exposure Federation adapters. They are explicit-selection
        # adapters, so generic federation queries do not consume contract APIs
        # or fetch onion pages unexpectedly.
        self.remote_source_adapter_registry.register(
            HibpBreachAdapter(service=self.breach_intelligence_service)
        )
        self.remote_source_adapter_registry.register(
            IntelligenceXMetadataAdapter(client=self.intelligencex_search_client)
        )
        self.remote_source_adapter_registry.register(
            TorPublicOnionAdapter(service=self.darkweb_intelligence_service)
        )

        # R13.13 — leak/paste and verified-scope exposure adapters.
        self.remote_source_adapter_registry.register(
            HibpPasteAdapter(client=self.hibp_extended_client)
        )
        self.remote_source_adapter_registry.register(
            HibpVerifiedDomainAdapter(client=self.hibp_extended_client)
        )
        self.remote_source_adapter_registry.register(
            HibpStealerLogEmailAdapter(client=self.hibp_extended_client)
        )
        self.remote_source_adapter_registry.register(
            HibpStealerLogEmailDomainAdapter(client=self.hibp_extended_client)
        )
        self.remote_source_adapter_registry.register(
            HibpStealerLogWebsiteDomainAdapter(client=self.hibp_extended_client)
        )
        self.remote_source_adapter_registry.register(
            GitHubSecretScanningAdapter(client=self.github_secret_scanning_client)
        )
        self.remote_source_adapter_registry.register(
            TorOnionDiscoveryAdapter(service=self.darkweb_discovery_service)
        )

        # R13.15 — Free Public Data Mega Pack 1.
        self.remote_source_adapter_registry.register(WikidataEntitySearchAdapter())
        self.remote_source_adapter_registry.register(OrcidPublicAdapter())
        self.remote_source_adapter_registry.register(
            NvdCveAdapter(api_key=settings.nvd_api_key)
        )
        self.remote_source_adapter_registry.register(
            OpenFdaAdapter(api_key=settings.openfda_api_key)
        )
        self.remote_source_adapter_registry.register(
            OpenFecAdapter(api_key=settings.fec_api_key)
        )
        self.remote_source_adapter_registry.register(IcijOffshoreLeaksAdapter())
        self.remote_source_adapter_registry.register(NppesNpiAdapter())

        # R13.16 — Low-Footprint Remote Data Mega Pack.
        self.remote_source_adapter_registry.register(GitHubPublicUserAdapter())
        self.remote_source_adapter_registry.register(GitLabPublicUserAdapter())
        self.remote_source_adapter_registry.register(SemanticScholarAdapter())
        self.remote_source_adapter_registry.register(EuropePmcAdapter())
        self.remote_source_adapter_registry.register(LibraryOfCongressAdapter())
        self.remote_source_adapter_registry.register(FbiWantedAdapter())
        self.remote_source_adapter_registry.register(FirstEpssAdapter())
        self.remote_source_adapter_registry.register(CirclHashlookupAdapter())
        self.remote_source_adapter_registry.register(ShodanInternetDbAdapter())
        self.remote_source_adapter_registry.register(CisaKevAdapter())

        # R13.17 — Low-Footprint Remote Data Mega Pack 2.
        self.remote_source_adapter_registry.register(RdapBootstrapAdapter())
        self.remote_source_adapter_registry.register(RipeStatAdapter())
        self.remote_source_adapter_registry.register(PeeringDbAdapter())
        self.remote_source_adapter_registry.register(GooglePublicDnsAdapter())
        self.remote_source_adapter_registry.register(UsaSpendingRecipientAdapter())
        self.remote_source_adapter_registry.register(FederalRegisterAdapter())
        self.remote_source_adapter_registry.register(DataCiteAdapter())
        self.remote_source_adapter_registry.register(ZenodoPublicAdapter())
        self.remote_source_adapter_registry.register(InternetArchiveMetadataAdapter())
        self.remote_source_adapter_registry.register(UnSecurityCouncilSanctionsAdapter())

        self.remote_source_adapter_service = RemoteSourceAdapterService(
            registry=self.remote_source_adapter_registry
        )
        self.exposure_intelligence_service = ExposureFederationService(
            remote_service=self.remote_source_adapter_service
        )
        self.exposure_persistence_service = ExposurePersistenceService(
            source_service=self.source_service,
            evidence_service=self.evidence_service,
            data_sanitizer=IntelligenceDataSanitizer(),
        )

        # M022 Registry Intelligence
        # ==================================================

        self.registry_provider_registry = RegistryProviderRegistry()
        self.gleif_registry_http_client = GleifRegistryHttpClient()
        self.gleif_registry_provider = GleifRegistryProvider(
            client=self.gleif_registry_http_client
        )
        self.registry_provider_registry.register(
            self.gleif_registry_provider
        )

        # R7 — EU VIES exact VAT-number validation.
        self.vies_registry_http_client = ViesRegistryHttpClient()
        self.vies_registry_provider = ViesRegistryProvider(
            client=self.vies_registry_http_client
        )
        self.registry_provider_registry.register(
            self.vies_registry_provider
        )

        # R5 — OpenCorporates aggregator (optional API token).
        opencorporates_token = (
            settings.opencorporates_api_token.get_secret_value()
            if settings.opencorporates_api_token is not None
            else None
        )
        self.opencorporates_http_client = OpenCorporatesHttpClient(
            api_token=opencorporates_token
        )
        self.opencorporates_registry_provider = OpenCorporatesRegistryProvider(
            client=self.opencorporates_http_client
        )
        self.registry_provider_registry.register(
            self.opencorporates_registry_provider
        )

        # R10 — CourtListener US case law (API v4, token-gated).
        courtlistener_token = (
            settings.courtlistener_api_token.get_secret_value()
            if settings.courtlistener_api_token is not None
            else None
        )
        self.courtlistener_http_client = CourtListenerHttpClient(
            api_token=courtlistener_token
        )
        self.courtlistener_registry_provider = CourtListenerRegistryProvider(
            client=self.courtlistener_http_client
        )
        self.registry_provider_registry.register(
            self.courtlistener_registry_provider
        )

        # R11 — free RECAP archive search + hard PACER purchase guard.
        self.courtlistener_recap_http_client = CourtListenerRecapHttpClient(
            api_token=courtlistener_token
        )
        self.courtlistener_recap_registry_provider = (
            CourtListenerRecapRegistryProvider(
                client=self.courtlistener_recap_http_client
            )
        )
        self.registry_provider_registry.register(
            self.courtlistener_recap_registry_provider
        )
        self.pacer_paid_fetch_guard = PacerPaidFetchGuard()

        # R12 — UK Companies House official Public Data API.
        companies_house_api_key = (
            settings.companies_house_api_key.get_secret_value()
            if settings.companies_house_api_key is not None
            else None
        )
        self.companies_house_http_client = CompaniesHouseHttpClient(
            api_key=companies_house_api_key
        )
        self.companies_house_registry_provider = CompaniesHouseRegistryProvider(
            client=self.companies_house_http_client
        )
        self.registry_provider_registry.register(
            self.companies_house_registry_provider
        )

        # R13 — Poland KRS official Open API.
        self.poland_krs_http_client = PolandKrsHttpClient()
        self.poland_krs_registry_provider = PolandKrsRegistryProvider(
            client=self.poland_krs_http_client
        )
        self.registry_provider_registry.register(
            self.poland_krs_registry_provider
        )

        # Large national datasets are never synchronized by end-user desktops.
        # The desktop provider delegates to the central Registry Backend and
        # receives only bounded normalized matches for the current query.
        registry_token = (
            settings.registry_api_token.get_secret_value()
            if settings.registry_api_token is not None
            else None
        )
        self.registry_api_client = RegistryApiHttpClient(
            base_url=settings.registry_api_url,
            token=registry_token,
            default_timeout=settings.registry_api_timeout,
        )
        self.ua_edr_registry_provider = RemoteRegistryProvider(
            info=UA_EDR_PROVIDER_INFO,
            client=self.registry_api_client,
        )
        self.registry_provider_registry.register(
            self.ua_edr_registry_provider
        )

        # Court-decision data follows the same remote-only boundary as EDR:
        # the desktop never reads the multi-million-row mirror directly.
        self.ua_edrsr_registry_provider = RemoteRegistryProvider(
            info=UA_EDRSR_PROVIDER_INFO,
            client=self.registry_api_client,
        )
        self.registry_provider_registry.register(
            self.ua_edrsr_registry_provider
        )

        self.registry_persistence_service = RegistryPersistenceService(
            source_service=self.source_service,
            evidence_service=self.evidence_service,
            entity_service=self.entity_service,
            evidence_link_service=self.evidence_link_service,
            search_indexing_service=self.search_indexing_service,
        )
        self.registry_intelligence_service = RegistryIntelligenceService(
            registry=self.registry_provider_registry,
            persistence_service=self.registry_persistence_service,
        )

        # ==================================================
        # Open-Web Discovery / Enrichment
        # M021.10
        # ==================================================

        self.open_web_provider_registry = (
            OpenWebProviderRegistry()
        )


        self.common_crawl_http_client = (
            CommonCrawlHttpClient()
        )


        self.common_crawl_raw_index_client = (
            CommonCrawlRawIndexClient()
        )
        self.common_crawl_metadata_client = (
            CommonCrawlMetadataClient(
                primary=self.common_crawl_http_client,
                raw_index=self.common_crawl_raw_index_client,
            )
        )

        self.common_crawl_open_web_provider = (
            CommonCrawlOpenWebProvider(
                client=(
                    self.common_crawl_metadata_client
                ),
            )
        )

        self.open_web_provider_registry.register(
            self.common_crawl_open_web_provider
        )

        # M021.16.7.3 — exact PHONE Open-Web discovery.
        # GDELT only discovers candidate public news URLs; every candidate is
        # re-fetched through bounded Live Web and exact-phone verified before
        # it can enter extraction/persistence.
        self.gdelt_phone_exact_open_web_provider = (
            GdeltPhoneExactOpenWebProvider()
        )
        self.open_web_provider_registry.register(
            self.gdelt_phone_exact_open_web_provider
        )

        self.searxng_phone_exact_open_web_provider = (
            SearxngPhoneExactOpenWebProvider()
        )
        self.open_web_provider_registry.register(
            self.searxng_phone_exact_open_web_provider
        )

        self.targeted_phone_public_sources_provider = (
            TargetedPhonePublicSourcesProvider()
        )
        self.open_web_provider_registry.register(
            self.targeted_phone_public_sources_provider
        )

        self.live_web_open_web_provider = (
            LiveWebOpenWebProvider()
        )

        self.open_web_provider_registry.register(
            self.live_web_open_web_provider
        )

        # M021.16.5.2A GDELT exact-email Open-Web registration
        from app.osint.open_web.providers.gdelt_exact_email import (
            GdeltExactEmailOpenWebProvider,
        )

        self.gdelt_exact_email_open_web_provider = (
            GdeltExactEmailOpenWebProvider(
                live_web_provider=self.live_web_open_web_provider,
            )
        )

        self.open_web_provider_registry.register(
            self.gdelt_exact_email_open_web_provider
        )

        # M021.16.5.2B Brave exact-email Open-Web registration
        from app.osint.open_web.providers.brave_exact_email import (
            BraveExactEmailOpenWebProvider,
        )

        self.brave_exact_email_open_web_provider = (
            BraveExactEmailOpenWebProvider(
                live_web_provider=self.live_web_open_web_provider,
            )
        )

        self.open_web_provider_registry.register(
            self.brave_exact_email_open_web_provider
        )

        self.open_web_discovery_service = (
            OpenWebDiscoveryService(
                registry=(
                    self.open_web_provider_registry
                ),
            )
        )

        self.open_web_identifier_extraction_bridge = (
            OpenWebIdentifierExtractionBridge(
                extraction_service=(
                    self.unified_extraction_service
                ),
            )
        )

        self.common_crawl_warc_content_client = (
            CommonCrawlWarcContentClient()
        )

        self.common_crawl_content_hydrator = (
            CommonCrawlContentHydrator(
                client=self.common_crawl_warc_content_client,
                max_documents=3,
                timeout=20,
            )
        )

        self.open_web_enrichment_service = (
            OpenWebEnrichmentService(
                discovery_service=(
                    self.open_web_discovery_service
                ),
                extraction_bridge=(
                    self.open_web_identifier_extraction_bridge
                ),
                persistence_service=(
                    self.osint_finding_persistence_service
                ),
                content_hydrator=(
                    self.common_crawl_content_hydrator
                ),
            )
        )

        self.osint_enrichment_service = (
            OsintEnrichmentService(
                execution_service=(
                    self.osint_enrichment_execution_service
                ),
                persistence_service=(
                    self.osint_finding_persistence_service
                ),
            )
        )

        self.investigation_target_enrichment_service = (
            InvestigationTargetEnrichmentService(
                execution_service=(
                    self.osint_enrichment_execution_service
                ),
                persistence_service=(
                    self.osint_finding_persistence_service
                ),
            )
        )

        self.osint_recursive_enrichment_service = (
            OsintRecursiveEnrichmentService(
                enrichment_service=(
                    self.osint_enrichment_service
                ),
            )
        )


        self.open_web_recursive_pivot_service = (
            OpenWebRecursivePivotService(
                recursive_service=(
                    self.osint_recursive_enrichment_service
                ),
            )
        )

        # ==================================================
        # Workflow
        # ==================================================

        self.workflow = (
            InvestigationWorkflow()
        )

        # ==================================================
        # Investigation Entity Resolution / Evidence Analysis
        # ==================================================

        self.entity_resolution_pipeline = (
            EntityResolutionPipeline(
                session
            )
        )

        self.investigation_entity_resolution_analysis_service = (
            InvestigationEntityResolutionAnalysisService(
                entity_service=(
                    self.entity_service
                ),
                entity_resolution_pipeline=(
                    self.entity_resolution_pipeline
                ),
            )
        )

        self.evidence_source_reliability_scoring_service = (
            SourceReliabilityScoringService()
        )

        self.evidence_strength_scoring_service = (
            EvidenceStrengthScoringService()
        )

        self.evidence_corroboration_service = (
            EvidenceCorroborationService()
        )

        self.evidence_contradiction_detection_service = (
            EvidenceContradictionDetectionService()
        )

        self.evidence_source_independence_service = (
            EvidenceSourceIndependenceService()
        )

        self.evidence_confidence_aggregation_service = (
            EvidenceConfidenceAggregationService()
        )

        self.evidence_confidence_explanation_service = (
            EvidenceConfidenceExplanationService()
        )

        self.investigation_evidence_confidence_service = (
            InvestigationEvidenceConfidenceService(
                strength_scoring_service=(
                    self.evidence_strength_scoring_service
                ),
                corroboration_service=(
                    self.evidence_corroboration_service
                ),
                contradiction_service=(
                    self.evidence_contradiction_detection_service
                ),
                source_independence_service=(
                    self.evidence_source_independence_service
                ),
                confidence_aggregation_service=(
                    self.evidence_confidence_aggregation_service
                ),
                explanation_service=(
                    self.evidence_confidence_explanation_service
                ),
            )
        )

        self.investigation_evidence_analysis_service = (
            InvestigationEvidenceAnalysisService(
                evidence_service=(
                    self.evidence_service
                ),
                source_reliability_scoring_service=(
                    self.evidence_source_reliability_scoring_service
                ),
                evidence_confidence_service=(
                    self.investigation_evidence_confidence_service
                ),
            )
        )

        # ==================================================
        # Investigation Graph Analysis
        # ==================================================

        self.unified_graph_analysis_service = (
            UnifiedGraphAnalysisService()
        )

        self.graph_explainability_service = (
            GraphExplainabilityService()
        )

        self.investigation_graph_analysis_service = (
            InvestigationGraphAnalysisService(
                entity_graph_service=(
                    self.entity_graph_service
                ),
                unified_graph_analysis_service=(
                    self.unified_graph_analysis_service
                ),
                graph_explainability_service=(
                    self.graph_explainability_service
                ),
            )
        )

        # ==================================================
        # Investigation Temporal Analysis
        # ==================================================

        self.unified_temporal_analysis_service = (
            UnifiedTemporalAnalysisService()
        )

        self.investigation_temporal_analysis_service = (
            InvestigationTemporalAnalysisService(
                timeline_service=(
                    self.timeline_service
                ),
                unified_temporal_analysis_service=(
                    self.unified_temporal_analysis_service
                ),
            )
        )

        # ==================================================
        # Investigation Anomaly Analysis
        # ==================================================

        self.investigation_entity_feature_extraction_service = (
            InvestigationEntityFeatureExtractionService()
        )

        self.unified_anomaly_analysis_service = (
            UnifiedAnomalyAnalysisService()
        )

        self.investigation_anomaly_analysis_service = (
            InvestigationAnomalyAnalysisService(
                investigation_graph_analysis_service=(
                    self.investigation_graph_analysis_service
                ),
                investigation_temporal_analysis_service=(
                    self.investigation_temporal_analysis_service
                ),
                entity_feature_extraction_service=(
                    self.investigation_entity_feature_extraction_service
                ),
                unified_anomaly_analysis_service=(
                    self.unified_anomaly_analysis_service
                ),
            )
        )

        # ==================================================
        # Investigation Entity Clustering
        # ==================================================

        self.investigation_entity_clustering_service = (
            InvestigationEntityClusteringService(
                investigation_graph_analysis_service=(
                    self.investigation_graph_analysis_service
                ),
                investigation_temporal_analysis_service=(
                    self.investigation_temporal_analysis_service
                ),
                entity_feature_extraction_service=(
                    self.investigation_entity_feature_extraction_service
                ),
            )
        )

        # ==================================================
        # Investigation Multimodal Analysis
        # ==================================================

        self.multimodal_image_aggregation_service = (
            MultimodalImageAggregationService()
        )

        self.investigation_multimodal_analysis_service = (
            InvestigationMultimodalAnalysisService(
                evidence_service=(
                    self.evidence_service
                ),
                image_aggregation_service=(
                    self.multimodal_image_aggregation_service
                ),
                audio_transcription_service=(
                    self.file_processing_router
                    .audio_processor
                    .transcription_service
                ),
                video_transcription_service=(
                    self.file_processing_router
                    .video_processor
                    .transcription_service
                ),
                video_frame_analysis_service=(
                    self.file_processing_router
                    .video_processor
                    .frame_analysis_service
                ),
            )
        )

        # ==================================================
        # Investigation Analysis Orchestrator
        # ==================================================

        self.investigation_analysis_orchestrator = (
            InvestigationAnalysisOrchestrator(
                case_service=(
                    self.case_service
                ),
                investigation_entity_resolution_analysis_service=(
                    self.investigation_entity_resolution_analysis_service
                ),
                investigation_evidence_analysis_service=(
                    self.investigation_evidence_analysis_service
                ),
                investigation_graph_analysis_service=(
                    self.investigation_graph_analysis_service
                ),
                investigation_temporal_analysis_service=(
                    self.investigation_temporal_analysis_service
                ),
                investigation_anomaly_analysis_service=(
                    self.investigation_anomaly_analysis_service
                ),
                investigation_entity_clustering_service=(
                    self.investigation_entity_clustering_service
                ),
                investigation_multimodal_analysis_service=(
                    self.investigation_multimodal_analysis_service
                ),
                investigation_rag_retrieval_service=(
                    self.investigation_rag_retrieval_service
                ),
                investigation_rag_context_builder=(
                    self.investigation_rag_context_builder
                ),
                investigation_rag_summary_service=(
                    self.investigation_rag_summary_service
                ),
                investigation_rag_conclusions_service=(
                    self.investigation_rag_conclusions_service
                ),
                investigation_rag_grounded_citation_service=(
                    self.investigation_rag_grounded_citation_service
                ),
                investigation_unified_analytical_context_service=(
                    self.investigation_unified_analytical_context_service
                ),
            )
        )

        # ==================================================
        # Investigation Analysis Runner
        # ==================================================

        self.investigation_analysis_runner = (
            InvestigationAnalysisRunner(
                orchestrator=(
                    self.investigation_analysis_orchestrator
                ),
            )
        )

        # ==================================================
        # Workspace Services
        # ==================================================

        self.case_workspace_service = (
            CaseWorkspaceService(
                case_service=(
                    self.case_service
                ),
                evidence_service=(
                    self.evidence_service
                ),
                entity_service=(
                    self.entity_service
                ),
                entity_graph_service=(
                    self.entity_graph_service
                ),
                message_service=(
                    self.message_service
                ),
                relationship_service=(
                    self.relationship_service
                ),
                timeline_service=(
                    self.timeline_service
                ),
                report_service=(
                    self.report_service
                ),
            )
        )


        self.import_workspace_service = (
            ImportWorkspaceService(
                case_service=(
                    self.case_service
                ),
                telegram_import_service=(
                    self.telegram_import_service
                ),
            )
        )

        self.osint_workspace_service = (
            OsintWorkspaceService(
                pipeline=(
                    self.osint_pipeline
                ),
                target_builder=(
                    self.osint_target_builder
                ),
            )
        )

        # ==================================================
        # Workspace Container
        # ==================================================

        self.workspaces = (
            ApplicationWorkspaces(
                case_workspace=(
                    self.case_workspace_service
                ),
                ai_workspace=(
                    self.ai_workspace_service
                ),
                import_workspace=(
                    self.import_workspace_service
                ),
                osint_workspace=(
                    self.osint_workspace_service
                ),
            )
        )

        # ==================================================
        # Application Service
        # ==================================================

        self.application_service = (
            InvestigationApplicationService(
                workflow=(
                    self.workflow
                ),
                workspaces=(
                    self.workspaces
                ),
                investigation_ai_service=(
                    self.investigation_ai_service
                ),
            )
        )

        # ==================================================
        # Controllers
        # ==================================================

        self.case_controller = (
            CaseController(
                container=self,
                case_service=(
                    self.case_service
                ),
                workspace_service=(
                    self.case_workspace_service
                ),
            )
        )

        self.workspace_controller = (
            WorkspaceController(
                container=self,
                workspace_service=(
                    self.case_workspace_service
                ),
            )
        )

        self.ai_controller = (
            AIAnalysisController(
                investigation_service=(
                    self.investigation_ai_service
                ),
                execution_service=(
                    self.ai_execution_service
                ),
                analyzer=(
                    self.ai_analyzer
                ),
            )
        )

        self.import_controller = (
            ImportController(
                import_service=(
                    self.import_workspace_service
                ),
            )
        )

        self.osint_controller = (
            OsintController(
                osint_service=(
                    self.osint_workspace_service
                ),
            )
        )

        self.image_gps_location_service = (
            ImageGpsLocationService(
                evidence_service=self.evidence_service,
                entity_service=self.entity_service,
                evidence_link_service=self.evidence_link_service,
            )
        )

    # ======================================================
    # Helpers
    # ======================================================

    def commit(
        self,
    ) -> None:
        """
        Commit current transaction.
        """

        self.session.commit()

    def rollback(
        self,
    ) -> None:
        """
        Rollback current transaction.
        """

        self.session.rollback()

    def close(
        self,
    ) -> None:
        """
        Close external clients and database session.
        """

        registry_client = getattr(self, "registry_api_client", None)
        if registry_client is not None:
            try:
                registry_client.close()
            except Exception:
                pass
        self.session.close()

