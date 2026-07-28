"""
Repository layer.

Repositories contain all database access logic.

Application services must use repositories
instead of working with SQLAlchemy sessions directly.
"""

from app.repositories.ai_analysis_repository import (
    AIAnalysisRepository,
)

from app.repositories.case_repository import (
    CaseRepository,
)

from app.repositories.document_repository import (
    DocumentRepository,
)

from app.repositories.entity_repository import (
    EntityRepository,
)

from app.repositories.evidence_repository import (
    EvidenceRepository,
)

from app.repositories.message_repository import (
    MessageRepository,
)

from app.repositories.relationship_repository import (
    RelationshipRepository,
)

from app.repositories.source_repository import (
    SourceRepository,
)



__all__ = [
    "AIAnalysisRepository",
    "CaseRepository",
    "DocumentRepository",
    "EntityRepository",
    "EvidenceRepository",
    "MessageRepository",
    "RelationshipRepository",
    "SourceRepository",
    "ReportRepository",
]