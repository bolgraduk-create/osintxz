"""
Full application integration test for the current application facade.

Checks application workflow integration with reporting and exporters without
requiring database, network or AI execution.
"""

import json

from app.application.investigation_manager import InvestigationManager
from app.application.services import InvestigationApplicationService
from app.application.workflow import InvestigationWorkflow
from app.exporters.html_exporter import HTMLExporter
from app.exporters.json_exporter import JSONExporter
from app.exporters.pdf_exporter import PDFExporter


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


def test_full_application_flow():
    manager = InvestigationManager()
    workflow = InvestigationWorkflow()

    def generate_report(data):
        return manager.run(data)

    workflow.add_step(generate_report)

    service = InvestigationApplicationService(
        workflow=workflow,
        investigation_ai_service=object(),
        workspaces=_FakeWorkspaces(),
    )

    result = service.execute(
        {
            "title": "Integration Case",
            "summary": "Full application test",
            "findings": [
                {
                    "entity": "John",
                }
            ],
        }
    )

    assert "report" in result

    report = result["report"]
    assert report.title == "Integration Case"

    json_result = JSONExporter().export(report)
    json_data = json.loads(json_result)
    assert json_data["title"] == "Integration Case"

    html_result = HTMLExporter().export(report)
    assert "<html>" in html_result

    pdf_result = PDFExporter().export(report)
    assert isinstance(pdf_result, bytes)
    assert pdf_result.startswith(b"%PDF")
