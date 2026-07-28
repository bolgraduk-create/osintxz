"""
Tests for InvestigationApplicationService.
"""


from app.application.services import (
    InvestigationApplicationService,
)



def test_application_service_execution():

    service = (
        InvestigationApplicationService()
    )



    def process(data):

        data["processed"] = True

        return data



    service.add_step(
        process
    )



    result = (
        service.execute_investigation(
            {}
        )
    )


    assert (
        result["processed"]
        is
        True
    )



def test_application_service_metadata():

    service = (
        InvestigationApplicationService()
    )


    metadata = (
        service.metadata()
    )


    assert (
        metadata["type"]
        ==
        "investigation_application_service"
    )


    assert (
        metadata["version"]
        ==
        "1.0"
    )