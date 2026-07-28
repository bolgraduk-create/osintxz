"""
Integration tests for Stage 19.

Tests complete investigation workflow.

Case
 ├── Source
 ├── Document
 ├── Entity
 ├── Relationship
 └── Evidence
"""

from __future__ import annotations

import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from app.database.init_db import init_database
from app.database.session import create_session

from app.repositories.case_repository import CaseRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.evidence_repository import EvidenceRepository

from app.models.case import Case
from app.models.document import Document, DocumentType
from app.models.entity import Entity, EntityType
from app.models.relationship import Relationship, RelationshipType
from app.models.evidence import Evidence, EvidenceType
from app.models.source import Source, SourceType, SourceStatus


def run_test() -> None:

    print("\n=== STAGE 19 TEST START ===\n")

    print("[STEP 1] Initializing database")
    init_database()
    print("[STEP 2] Database initialized")

    session = create_session()

    print("[STEP 3] Session created")

    try:

        case_repository = CaseRepository(session)
        document_repository = DocumentRepository(session)
        entity_repository = EntityRepository(session)
        relationship_repository = RelationshipRepository(session)
        evidence_repository = EvidenceRepository(session)

        print("[STEP 4] Repositories created")

        # ----------------------------------------------------
        # CASE
        # ----------------------------------------------------

        case = Case(
            title="Test Investigation",
            description="Stage 19 integration test",
        )

        case_repository.create(case)

        print("[OK] Case created")

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        source = Source(
            case_id=case.id,
            source_type=SourceType.FILE,
            status=SourceStatus.IMPORTED,
            name="Telegram Export",
        )

        session.add(source)
        session.flush()

        print("[OK] Source created")

        # ----------------------------------------------------
        # DOCUMENT
        # ----------------------------------------------------

        document = Document(
            case_id=case.id,
            source_id=source.id,
            document_type=DocumentType.TXT,
            title="Telegram Export",
            content="Example investigation document",
        )

        document_repository.create(document)

        documents = document_repository.get_by_case(case.id)

        assert len(documents) == 1

        print("[OK] Document created")

        # ----------------------------------------------------
        # ENTITIES
        # ----------------------------------------------------

        person = Entity(
            case_id=case.id,
            entity_type=EntityType.PERSON,
            value="John Doe",
        )

        location = Entity(
            case_id=case.id,
            entity_type=EntityType.LOCATION,
            value="Berlin",
        )

        entity_repository.create(person)
        entity_repository.create(location)

        entities = entity_repository.get_by_case(case.id)

        assert len(entities) == 2

        print("[OK] Entities created")

        # ----------------------------------------------------
        # RELATIONSHIP
        # ----------------------------------------------------

        relationship = Relationship(
            case_id=case.id,
            source_entity_id=person.id,
            target_entity_id=location.id,
            relationship_type=RelationshipType.LOCATED_AT,
        )

        relationship_repository.create(relationship)

        relations = relationship_repository.get_by_case(case.id)

        assert len(relations) == 1

        print("[OK] Relationship created")

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        evidence = Evidence(
            case_id=case.id,
            source_id=source.id,
            evidence_type=EvidenceType.MESSAGE,
            title="Telegram message",
            value="Message proving connection",
        )

        evidence_repository.create(evidence)

        evidences = evidence_repository.get_by_case(case.id)

        assert len(evidences) == 1

        print("[OK] Evidence created")

        print("\n========== RESULT ==========")

        print("Case:", case.title)
        print("Documents:", len(documents))
        print("Entities:", len(entities))
        print("Relationships:", len(relations))
        print("Evidence:", len(evidences))

        print("\n=== STAGE 19 TEST PASSED ===")

    finally:
        session.close()


if __name__ == "__main__":
    run_test()