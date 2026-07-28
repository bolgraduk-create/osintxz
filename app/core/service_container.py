"""
Application Service Container.

Responsible for:

- creating application services
- creating AI layer
- creating controllers
- dependency injection

This is the single composition root
for the whole application.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.ai_factory import (
    create_ai_analyzer,
)

from app.services.case_service import (
    CaseService,
)

from app.services.source_service import (
    SourceService,
)

from app.services.evidence_service import (
    EvidenceService,
)

from app.services.entity_service import (
    EntityService,
)

from app.services.relationship_service import (
    RelationshipService,
)

from app.services.report_service import (
    ReportService,
)


from app.services.collection_service import (
    CollectionService,
)

from app.services.evidence_processing_service import (
    EvidenceProcessingService,
)

from app.services.telegram_import_service import (
    TelegramImportService,
)

from app.collectors.telegram.telegram_collector import (
    TelegramCollector,
)

from app.application.case_workspace_service import (
    CaseWorkspaceService,
)

from app.application.ai_workspace_service import (
    AIWorkspaceService,
)

from app.application.investigation_ai_service import (
    InvestigationAIService,
)

from app.controllers.case_controller import (
    CaseController,
)

from app.controllers.workspace_controller import (
    WorkspaceController,
)

from app.controllers.ai_analysis_controller import (
    AIAnalysisController,
)

from app.application.import_workspace_service import (
    ImportWorkspaceService,
)


class ServiceContainer:
    """
    Central application container.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:

        self.session = session

        # ======================================================
        # AI
        # ======================================================

        self.ai_analyzer = (
            create_ai_analyzer()
        )

        # ======================================================
        # Domain services
        # ======================================================

        self.case_service = CaseService(
            session
        )

        self.source_service = SourceService(
            session
        )

        self.evidence_service = EvidenceService(
            session
        )

        self.entity_service = EntityService(
            session
        )

        self.relationship_service = RelationshipService(
            session
        )

        self.report_service = ReportService(
            session
        )



        # ======================================================
        # Import pipeline
        # ======================================================

        self.telegram_collector = (
            TelegramCollector()
        )

        self.collection_service = (
            CollectionService(
                evidence_repository=self.evidence_service.repository,
            )
        )

        self.evidence_processing_service = (
            EvidenceProcessingService(
                entity_service=self.entity_service,
                relationship_service=self.relationship_service,
                timeline_service=self.timeline_service,
                report_service=self.report_service,
                ai_service=self.investigation_ai_service,
            )
        )

        self.telegram_import_service = (
            TelegramImportService(
                collector=self.telegram_collector,
                collection_service=self.collection_service,
                processing_service=self.evidence_processing_service,
            )
        )

        # ======================================================
        # Application services
        # ======================================================

        self.case_workspace_service = (
            CaseWorkspaceService(
                case_service=self.case_service,
                evidence_service=self.evidence_service,
                entity_service=self.entity_service,
                relationship_service=self.relationship_service,
                report_service=self.report_service,
            )
        )

        self.ai_workspace_service = (
            AIWorkspaceService(
                case_service=self.case_service,
            )
        )

        self.import_workspace_service = (
            ImportWorkspaceService(
                case_service=self.case_service,
                telegram_import_service=self.telegram_import_service,
            )
        )

        self.investigation_ai_service = (
            InvestigationAIService(
                workspace_service=self.ai_workspace_service,
            )
        )

        # ======================================================
        # Controllers
        # ======================================================

        self.case_controller = (
            CaseController(
                container=self,
                case_service=self.case_service,
                workspace_service=self.case_workspace_service,
            )
        )

        self.workspace_controller = (
            WorkspaceController(
                container=self,
                workspace_service=self.case_workspace_service,
            )
        )

        self.ai_controller = (
            AIAnalysisController(
                investigation_service=self.investigation_ai_service,
                analyzer=self.ai_analyzer,
            )
        )