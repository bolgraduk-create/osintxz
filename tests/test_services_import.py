"""
Service layer import test.

Checks that:

- models load correctly
- repositories load correctly
- services load correctly

No database connection required.
"""


def test_service_imports():

    from app.models import (
        Case,
        Source,
        Evidence,
        Document,
        Entity,
        Message,
        Relationship,
        AIAnalysis,
    )

    from app.repositories import (
        CaseRepository,
        SourceRepository,
        EvidenceRepository,
        DocumentRepository,
        EntityRepository,
        MessageRepository,
        RelationshipRepository,
        AIAnalysisRepository,
    )

    from app.services import (
        CaseService,
        SourceService,
        EvidenceService,
        DocumentService,
        EntityService,
        MessageService,
        RelationshipService,
        AIAnalysisService,
        ReportService,
    )


    assert Case
    assert Source
    assert Evidence
    assert Document
    assert Entity
    assert Message
    assert Relationship
    assert AIAnalysis


    assert CaseRepository
    assert SourceRepository
    assert EvidenceRepository
    assert DocumentRepository
    assert EntityRepository
    assert MessageRepository
    assert RelationshipRepository
    assert AIAnalysisRepository


    assert CaseService
    assert SourceService
    assert EvidenceService
    assert DocumentService
    assert EntityService
    assert MessageService
    assert RelationshipService
    assert AIAnalysisService
    assert ReportService