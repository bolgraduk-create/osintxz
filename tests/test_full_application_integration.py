"""
Full application integration tests.

Checks application layer connection
with reporting and export layers.
"""


import json


from app.application.services import (
    InvestigationApplicationService,
)


from app.application.workflow import (
    InvestigationWorkflow,
)


from app.application.investigation_manager import (
    InvestigationManager,
)


from app.exporters.json_exporter import (
    JSONExporter,
)


from app.exporters.html_exporter import (
    HTMLExporter,
)


from app.exporters.pdf_exporter import (
    PDFExporter,
)



def test_full_application_flow():

    # ==========================================================
    # Create manager
    # ==========================================================

    manager = InvestigationManager()



    # ==========================================================
    # Create workflow
    # ==========================================================

    workflow = InvestigationWorkflow()



    def generate_report(
        data,
    ):

        result = (
            manager.run(
                data
            )
        )

        return result



    workflow.add_step(
        generate_report
    )



    # ==========================================================
    # Create application service
    # ==========================================================

    service = InvestigationApplicationService(
        workflow
    )



    result = (
        service.execute_investigation(
            {

                "title":
                    "Integration Case",


                "summary":
                    "Full application test",


                "findings":
                    [
                        {
                            "entity":
                                "John"
                        }
                    ],

            }
        )
    )



    assert (
        "report"
        in
        result
    )


    report = (
        result["report"]
    )


    assert (
        report.title
        ==
        "Integration Case"
    )



    # ==========================================================
    # Export verification
    # ==========================================================

    json_result = (
        JSONExporter()
        .export(
            report
        )
    )


    json_data = json.loads(
        json_result
    )


    assert (
        json_data["title"]
        ==
        "Integration Case"
    )



    html_result = (
        HTMLExporter()
        .export(
            report
        )
    )


    assert (
        "<html>"
        in
        html_result
    )



    pdf_result = (
        PDFExporter()
        .export(
            report
        )
    )


    assert isinstance(
        pdf_result,
        bytes,
    )


    assert (
        pdf_result.startswith(
            b"%PDF"
        )
    )