"""
Telegram import service.

Coordinates Telegram import pipeline.

Pipeline:

Telegram Export
        ↓
TelegramCollector
        ↓
CollectedItems
        ↓
CollectionService
        ↓
TelegramEntityImportService
        ↓
TelegramRelationshipImportService
        ↓
TelegramTimelineImportService
        ↓
TelegramReportImportService
        ↓
SearchIndexingService
        ↓
Unified Search indexes

Full investigation AI processing is started separately
after its individual stages are verified.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.collectors.telegram.telegram_collector import (
    TelegramCollector,
)

from app.models.source import (
    SourceType,
)

from app.services.collection_service import (
    CollectionService,
)

from app.services.unified_extraction_service import (
    UnifiedExtractionService,
)

from app.services.search_indexing_service import (
    SearchIndexingService,
)

from app.services.source_service import (
    SourceService,
)

from app.services.telegram_entity_import_service import (
    TelegramEntityImportService,
)

from app.services.telegram_relationship_import_service import (
    TelegramRelationshipImportService,
)

from app.services.telegram_timeline_import_service import (
    TelegramTimelineImportService,
)

from app.services.telegram_report_import_service import (
    TelegramReportImportService,
)


class TelegramImportService:
    """
    Imports Telegram export into investigation.
    """

    def __init__(
        self,
        collector: TelegramCollector,
        collection_service: CollectionService,
        extraction_service: UnifiedExtractionService,
        source_service: SourceService,
        entity_import_service: TelegramEntityImportService,
        relationship_import_service: (
            TelegramRelationshipImportService
        ),
        timeline_import_service: (
            TelegramTimelineImportService
        ),
        report_import_service: (
            TelegramReportImportService
        ),
        search_indexing_service: SearchIndexingService,
    ) -> None:

        self.collector = collector

        self.collection_service = (
            collection_service
        )

        self.extraction_service = (
            extraction_service
        )

        self.source_service = (
            source_service
        )

        self.entity_import_service = (
            entity_import_service
        )

        self.relationship_import_service = (
            relationship_import_service
        )

        self.timeline_import_service = (
            timeline_import_service
        )

        self.report_import_service = (
            report_import_service
        )

        self.search_indexing_service = (
            search_indexing_service
        )

    # ==========================================================
    # Public API
    # ==========================================================

    def import_export(
        self,
        case_id: UUID,
        export_path: str | Path,
    ) -> dict:
        """
        Import Telegram export into a case.

        Returns collection, entity, relationship,
        timeline, report and search indexing statistics.

        Search indexing is finalized only after all
        Telegram import stages have completed.

        This prevents one semantic embedding request
        from being executed for every imported message.
        """

        export_path = Path(
            export_path
        )

        if not self.can_import(
            export_path
        ):

            raise ValueError(
                "Selected path is not a valid "
                "Telegram result.json export."
            )

        # ------------------------------------------------------
        # Collection
        # ------------------------------------------------------

        items = self.collector.collect(
            export_path
        )

        # ------------------------------------------------------
        # Source
        # ------------------------------------------------------

        source = (
            self.source_service
            .create_source(
                case_id=case_id,
                name=self._get_source_name(
                    export_path
                ),
                source_type=(
                    SourceType.TELEGRAM
                ),
                path=str(
                    export_path
                ),
                description=(
                    "Imported Telegram export"
                ),
            )
        )

        # ------------------------------------------------------
        # Raw investigation objects
        # ------------------------------------------------------

        self.collection_service.collect_many(
            case_id=case_id,
            source_id=source.id,
            items=items,
        )

        # ------------------------------------------------------
        # Message identifier extraction
        # ------------------------------------------------------

        identifier_statistics = (
            self.extraction_service
            .extract_case_messages(
                case_id=case_id,
                source_id=source.id,
            )
        )

        # ------------------------------------------------------
        # Entities
        # ------------------------------------------------------

        entity_statistics = (
            self.entity_import_service
            .import_entities(
                case_id=case_id,
                items=items,
            )
        )

        # ------------------------------------------------------
        # Relationships
        # ------------------------------------------------------

        relationship_statistics = (
            self.relationship_import_service
            .import_relationships(
                case_id=case_id,
                items=items,
            )
        )

        # ------------------------------------------------------
        # Timeline
        # ------------------------------------------------------

        timeline_statistics = (
            self.timeline_import_service
            .import_events(
                case_id=case_id,
                items=items,
            )
        )

        # ------------------------------------------------------
        # Reports
        # ------------------------------------------------------

        report_statistics = (
            self.report_import_service
            .import_reports(
                case_id=case_id,
            )
        )

        # ------------------------------------------------------
        # Unified Search indexing
        # ------------------------------------------------------
        #
        # During collection, high-volume objects such as
        # messages receive lightweight SearchIndex updates.
        #
        # Only after the complete import is finished do we:
        #
        # - backfill any objects not indexed by their domain
        #   service
        # - index generated entities
        # - index generated reports
        # - generate missing embeddings in batches
        #
        # Existing SearchIndex and SearchEmbedding rows are
        # skipped by the indexing infrastructure.
        # ------------------------------------------------------

        search_statistics = (
            self.search_indexing_service
            .index_case(
                case_id
            )
        )

        # ------------------------------------------------------
        # Post-import analysis
        # ------------------------------------------------------
        # Full investigation analysis is intentionally not run
        # inside Telegram import. The caller may invoke the
        # application-level InvestigationAnalysisRunner after the
        # import transaction has completed successfully.

        # ------------------------------------------------------
        # Result
        # ------------------------------------------------------

        return {
            "source_id": str(
                source.id
            ),

            "items_imported": len(
                items
            ),

            # --------------------------------------------------
            # Extracted identifiers
            # --------------------------------------------------

            "identifiers_found": (
                identifier_statistics[
                    "extracted_candidates"
                ]
            ),

            "identifiers_created": (
                identifier_statistics[
                    "created_entities"
                ]
            ),

            "identifiers_existing": (
                identifier_statistics[
                    "existing_entities"
                ]
            ),

            "identifiers_skipped_oversized": (
                identifier_statistics[
                    "skipped_oversized"
                ]
            ),

            "identifiers_created_by_type": (
                identifier_statistics[
                    "created_by_type"
                ]
            ),

            "identifier_provenance_evidence_created": (
                identifier_statistics[
                    "provenance_evidence_created"
                ]
            ),

            "identifier_provenance_evidence_existing": (
                identifier_statistics[
                    "provenance_evidence_existing"
                ]
            ),

            "identifier_evidence_links_created": (
                identifier_statistics[
                    "evidence_links_created"
                ]
            ),

            "identifier_evidence_links_existing": (
                identifier_statistics[
                    "evidence_links_existing"
                ]
            ),

            # --------------------------------------------------
            # Entities
            # --------------------------------------------------

            "entities_found": (
                entity_statistics[
                    "found"
                ]
            ),

            "entities_created": (
                entity_statistics[
                    "created"
                ]
            ),

            "entities_skipped": (
                entity_statistics[
                    "skipped"
                ]
            ),

            # --------------------------------------------------
            # Relationships
            # --------------------------------------------------

            "relationships_found": (
                relationship_statistics[
                    "found"
                ]
            ),

            "relationships_created": (
                relationship_statistics[
                    "created"
                ]
            ),

            "relationships_skipped": (
                relationship_statistics[
                    "skipped"
                ]
            ),

            "relationships_unresolved": (
                relationship_statistics[
                    "unresolved"
                ]
            ),

            # --------------------------------------------------
            # Timeline
            # --------------------------------------------------

            "timeline_found": (
                timeline_statistics[
                    "found"
                ]
            ),

            "timeline_created": (
                timeline_statistics[
                    "created"
                ]
            ),

            "timeline_skipped": (
                timeline_statistics[
                    "skipped"
                ]
            ),

            "timeline_unresolved": (
                timeline_statistics[
                    "unresolved"
                ]
            ),

            # --------------------------------------------------
            # Reports
            # --------------------------------------------------

            "reports_found": (
                report_statistics[
                    "found"
                ]
            ),

            "reports_created": (
                report_statistics[
                    "created"
                ]
            ),

            "reports_updated": (
                report_statistics[
                    "updated"
                ]
            ),

            "reports_skipped": (
                report_statistics[
                    "skipped"
                ]
            ),

            "summary_report_id": (
                report_statistics[
                    "report_id"
                ]
            ),

            # --------------------------------------------------
            # Search indexes
            # --------------------------------------------------

            "search_indexes_processed": (
                search_statistics
                .search_indexes
                .processed
            ),

            "search_indexes_created": (
                search_statistics
                .search_indexes
                .created
            ),

            "search_indexes_updated": (
                search_statistics
                .search_indexes
                .updated
            ),

            "search_indexes_skipped": (
                search_statistics
                .search_indexes
                .skipped
            ),

            "search_indexes_failed": (
                search_statistics
                .search_indexes
                .failed
            ),

            # --------------------------------------------------
            # Semantic embeddings
            # --------------------------------------------------

            "search_embeddings_processed": (
                search_statistics
                .embeddings
                .processed
            ),

            "search_embeddings_created_or_updated": (
                search_statistics
                .embeddings
                .created_or_updated
            ),

            "search_embeddings_skipped": (
                search_statistics
                .embeddings
                .skipped
            ),

            "search_embeddings_failed": (
                search_statistics
                .embeddings
                .failed
            ),

            "search_indexing_successful": (
                search_statistics
                .successful
            ),
        }

    # ==========================================================
    # Validation
    # ==========================================================

    def can_import(
        self,
        export_path: str | Path,
    ) -> bool:
        """
        Validate Telegram export path.
        """

        path = Path(
            export_path
        )

        if path.is_dir():

            result_file = (
                path
                / "result.json"
            )

            return (
                result_file.is_file()
            )

        return (
            path.is_file()
            and path.suffix.lower()
            == ".json"
        )

    # ==========================================================
    # Compatibility wrappers
    # ==========================================================

    def import_directory(
        self,
        case_id: UUID,
        directory: str | Path,
    ) -> dict:
        """
        Import Telegram export directory.
        """

        return self.import_export(
            case_id=case_id,
            export_path=directory,
        )

    def import_file(
        self,
        case_id: UUID,
        file_path: str | Path,
    ) -> dict:
        """
        Import Telegram result.json file.
        """

        return self.import_export(
            case_id=case_id,
            export_path=file_path,
        )

    def collect_only(
        self,
        export_path: str | Path,
    ):
        """
        Collect Telegram objects without
        storing them in the database.
        """

        return self.collector.collect(
            export_path
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def _get_source_name(
        self,
        export_path: Path,
    ) -> str:
        """
        Build readable source name.
        """

        if export_path.is_dir():

            return (
                export_path.name
                or "Telegram Export"
            )

        parent_name = (
            export_path.parent.name
        )

        if parent_name:

            return parent_name

        return "Telegram Export"
