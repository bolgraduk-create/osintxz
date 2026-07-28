"""
AI investigation service.

Coordinates AI analysis workflow.

Responsibilities:

- collect investigation context
- send context to AI provider
- save AI analysis result

Does NOT:

- manage providers
- create AI clients
- parse documents
"""

from __future__ import annotations


from uuid import UUID


from app.models.ai_analysis import (
    AIAnalysis,
    AnalysisType,
)



class AIInvestigationService:
    """
    Runs AI analysis for investigations.
    """


    def __init__(
        self,
        ai_manager=None,
        ai_provider=None,
        session=None,
        ai_analysis_repository=None,
        case_repository=None,
        evidence_repository=None,
        entity_repository=None,
        relationship_repository=None,
        report_repository=None,
    ):
        """
        Initialize service.
        """


        self.ai_manager = (
            ai_manager
            if ai_manager
            else ai_provider
        )


        self.session = session


        if session:

            from app.repositories.ai_analysis_repository import (
                AIAnalysisRepository
            )

            from app.repositories.case_repository import (
                CaseRepository
            )

            from app.repositories.evidence_repository import (
                EvidenceRepository
            )

            from app.repositories.entity_repository import (
                EntityRepository
            )

            from app.repositories.relationship_repository import (
                RelationshipRepository
            )

            from app.repositories.report_repository import (
                ReportRepository
            )


            self.ai_analysis_repository = (
                ai_analysis_repository
                or AIAnalysisRepository(session)
            )

            self.case_repository = (
                case_repository
                or CaseRepository(session)
            )

            self.evidence_repository = (
                evidence_repository
                or EvidenceRepository(session)
            )

            self.entity_repository = (
                entity_repository
                or EntityRepository(session)
            )

            self.relationship_repository = (
                relationship_repository
                or RelationshipRepository(session)
            )

            self.report_repository = (
                report_repository
                or ReportRepository(session)
            )


        else:

            self.ai_analysis_repository = (
                ai_analysis_repository
            )

            self.case_repository = (
                case_repository
            )

            self.evidence_repository = (
                evidence_repository
            )

            self.entity_repository = (
                entity_repository
            )

            self.relationship_repository = (
                relationship_repository
            )

            self.report_repository = (
                report_repository
            )



    def analyze(
        self,
        case_id: UUID,
        prompt: str | None = None,
    ) -> AIAnalysis:
        """
        Run AI analysis for case.
        """


        case = self.case_repository.get(
            case_id
        )


        if not case:
            raise ValueError(
                "Case not found"
            )



        evidence = (
            self.evidence_repository
            .get_by_case(case_id)
        )


        entities = (
            self.entity_repository
            .get_by_case(case_id)
        )


        relationships = (
            self.relationship_repository
            .get_by_case(case_id)
        )


        reports = (
            self.report_repository
            .get_by_case(case_id)
        )



        context = {

            "case": {

                "id":
                    str(case.id),

                "title":
                    case.title,

                "description":
                    case.description,

            },


            "evidence": [

                {

                    "title":
                        item.title,

                    "type":
                        str(item.evidence_type),

                    "value":
                        item.value,

                }

                for item in evidence

            ],


            "entities": [

                {

                    "type":
                        str(item.entity_type),

                    "value":
                        item.value,

                }

                for item in entities

            ],


            "relationships": [

                {

                    "type":
                        str(item.relationship_type),

                    "confidence":
                        item.confidence,

                }

                for item in relationships

            ],


            "reports": [

                {

                    "title":
                        item.title,

                    "type":
                        str(item.report_type),

                }

                for item in reports

            ],

        }



        ai_prompt = (

            prompt

            if prompt

            else

            "Analyze this investigation data."

        )



        response = (
            self.ai_manager.generate(
                prompt=f"""
{ai_prompt}

Investigation data:

{context}
"""
            )
        )



        if hasattr(
            self.ai_manager,
            "get_model_info"
        ):

            model_info = (
                self.ai_manager
                .get_model_info()
            )

        else:

            model_info = (
                self.ai_manager
                .__class__
                .__name__
            )



        analysis = (
            self.ai_analysis_repository.create(

                case_id=case_id,

                analysis_type=
                    AnalysisType.OTHER,

                model_name=
                    str(model_info),

                result=
                    response,

                confidence=
                    1.0,

                metadata_json=
                    str(
                        {
                            "provider":
                                str(model_info),

                            "service":
                                "AIInvestigationService",

                        }
                    ),
            )
        )


        return analysis