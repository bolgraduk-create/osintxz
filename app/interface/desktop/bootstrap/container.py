"""
Desktop dependency container.

Creates and stores application components.

Does NOT:

- contain business logic
- execute workflows
- access UI directly
"""

from __future__ import annotations


from app.database.session import (
    create_session,
)


from app.services.case_service import (
    CaseService,
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


from app.application.case_workspace_service import (
    CaseWorkspaceService,
)


from app.application.services import (
    InvestigationApplicationService,
)


from app.interface.controllers import (
    InvestigationController,
)



class DesktopContainer:
    """
    Dependency container for desktop application.
    """



    def __init__(
        self,
    ):

        self.session = (
            create_session()
        )


        # ======================================================
        # Domain services
        # ======================================================

        self.case_service = CaseService(
            self.session
        )


        self.evidence_service = EvidenceService(
            self.session
        )


        self.entity_service = EntityService(
            self.session
        )


        self.relationship_service = RelationshipService(
            self.session
        )


        self.report_service = ReportService(
            self.session
        )



        # ======================================================
        # Application services
        # ======================================================

        self.workspace_service = (
            CaseWorkspaceService(

                case_service=self.case_service,

                evidence_service=self.evidence_service,

                entity_service=self.entity_service,

                relationship_service=self.relationship_service,

                report_service=self.report_service,

            )
        )


        self.investigation_service = (
            InvestigationApplicationService(

                case_service=self.case_service,

                workspace_service=self.workspace_service,

            )
        )



        # ======================================================
        # Controllers
        # ======================================================

        self.investigation_controller = (
            InvestigationController(
                self.investigation_service
            )
        )