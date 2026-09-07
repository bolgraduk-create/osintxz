"""
Entity resolution pipeline delegation tests.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.entity import EntityType
from app.services.entity_resolution_pipeline import EntityResolutionPipeline


class FakeEntity:
    def __init__(
        self,
        value: str,
        entity_type: EntityType,
        *,
        case_id=None,
    ) -> None:
        self.id = uuid4()
        self.case_id = case_id or uuid4()
        self.value = value
        self.entity_type = entity_type
        self.normalized_value = None
        self.metadata_json = None


def test_pipeline_calls_resolver():
    session = MagicMock()
    pipeline = EntityResolutionPipeline(session)
    case_id = uuid4()

    first = FakeEntity(
        "test@mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )
    second = FakeEntity(
        "test@mail.com",
        EntityType.EMAIL,
        case_id=case_id,
    )

    expected = MagicMock()

    with patch.object(
        pipeline.resolver,
        "resolve_pair",
        return_value=expected,
    ) as resolver_mock:
        result = pipeline.process_pair(
            first,
            second,
        )

    assert result is expected
    resolver_mock.assert_called_once_with(
        first,
        second,
        evidence_observations=None,
    )
