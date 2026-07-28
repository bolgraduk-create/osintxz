"""
Tests for InvestigationController.
"""


from app.interface.controllers import (
    InvestigationController,
)



class MockService:
    """
    Fake application service.
    """

    def execute_investigation(
        self,
        data,
    ):

        return {

            "received":
                data

        }



def test_controller_handle():

    controller = (
        InvestigationController(
            MockService()
        )
    )


    result = controller.handle(
        {
            "case":
                "test"
        }
    )


    assert (
        result["received"]["case"]
        ==
        "test"
    )



def test_controller_create():

    controller = (
        InvestigationController(
            MockService()
        )
    )


    result = (
        controller.create_investigation(
            {
                "id":
                    1
            }
        )
    )


    assert (
        result["received"]["id"]
        ==
        1
    )