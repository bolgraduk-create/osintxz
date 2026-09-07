"""
Tests for the current InvestigationApplicationService facade.
"""

from app.application.services import InvestigationApplicationService
from app.application.workflow import InvestigationWorkflow


class _FakeWorkspaces:
    """Small ApplicationWorkspaces-compatible test double."""

    def __init__(self) -> None:
        self.case = object()
        self.ai = object()
        self.imports = object()

    def metadata(self) -> dict:
        return {
            "case": {"type": "test_case_workspace"},
            "ai": {"type": "test_ai_workspace"},
            "imports": {"type": "test_import_workspace"},
        }

    def get(self, name: str):
        return {
            "case": self.case,
            "ai": self.ai,
            "imports": self.imports,
        }.get(name)

    def names(self) -> list[str]:
        return ["case", "ai", "imports"]


def _build_service(
    workflow: InvestigationWorkflow | None = None,
) -> InvestigationApplicationService:
    return InvestigationApplicationService(
        workflow=workflow or InvestigationWorkflow(),
        investigation_ai_service=object(),
        workspaces=_FakeWorkspaces(),
    )


def test_application_service_execution():
    workflow = InvestigationWorkflow()

    def process(data):
        data["processed"] = True
        return data

    workflow.add_step(process)
    service = _build_service(workflow)

    result = service.execute({})

    assert result["processed"] is True


def test_application_service_metadata():
    service = _build_service()
    metadata = service.metadata()

    assert metadata["type"] == "investigation_application_service"
    assert metadata["version"] == "3.0"
    assert "workspaces" in metadata
