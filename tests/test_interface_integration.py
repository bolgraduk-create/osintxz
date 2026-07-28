"""
Interface integration tests.

Checks full flow:

CLI
 ↓
Controller
 ↓
Application Service
 ↓
Workflow
"""



from app.interface.cli import (
    CLIInterface,
)


from app.interface.controllers import (
    InvestigationController,
)


from app.application.services import (
    InvestigationApplicationService,
)


from app.application.workflow import (
    InvestigationWorkflow,
)



def test_full_interface_flow():


    # ==========================================================
    # Application workflow
    # ==========================================================

    workflow = InvestigationWorkflow()



    def process_request(
        data,
    ):

        data["processed"] = True

        return data



    workflow.add_step(
        process_request
    )



    # ==========================================================
    # Application service
    # ==========================================================

    service = InvestigationApplicationService(
        workflow
    )



    # ==========================================================
    # Controller
    # ==========================================================

    controller = InvestigationController(
        service
    )



    # ==========================================================
    # CLI
    # ==========================================================

    cli = CLIInterface(
        controller.handle
    )



    result = cli.execute_command(
        {
            "case":
                "integration_test"
        }
    )



    assert (
        result["processed"]
        is
        True
    )


    assert (
        result["case"]
        ==
        "integration_test"
    )