"""
Legacy CLI/controller transport integration with the current application facade.

The old interface controller still speaks the historical
``execute_investigation`` service protocol.  The test keeps that legacy
transport isolated behind a test-only adapter while validating that the real
current InvestigationApplicationService and workflow perform the work.
"""

from app.application.services import InvestigationApplicationService
from app.application.workflow import InvestigationWorkflow
from app.interface.cli import CLIInterface
from app.interface.controllers import InvestigationController


class _FakeWorkspaces:
    def __init__(self) -> None:
        self.case = object()
        self.ai = object()
        self.imports = object()

    def metadata(self) -> dict:
        return {}

    def get(self, name: str):
        return None

    def names(self) -> list[str]:
        return []


class _LegacyControllerServiceAdapter:
    """Bridge the legacy controller protocol to the current facade API."""

    def __init__(
        self,
        service: InvestigationApplicationService,
    ) -> None:
        self.service = service

    def execute_investigation(self, data):
        return self.service.execute(data)


def test_full_interface_flow():
    workflow = InvestigationWorkflow()

    def process_request(data):
        data["processed"] = True
        return data

    workflow.add_step(process_request)

    service = InvestigationApplicationService(
        workflow=workflow,
        investigation_ai_service=object(),
        workspaces=_FakeWorkspaces(),
    )

    controller = InvestigationController(
        _LegacyControllerServiceAdapter(service)
    )

    cli = CLIInterface(controller.handle)

    result = cli.execute_command(
        {
            "case": "integration_test",
        }
    )

    assert result["processed"] is True
    assert result["case"] == "integration_test"
