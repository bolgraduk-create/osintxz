"""
Tests for InvestigationManager.
"""


from app.application.investigation_manager import (
    InvestigationManager,
)



def test_investigation_workflow():

    manager = InvestigationManager()


    result = manager.run(
        {

            "title":
                "Test Case",


            "summary":
                "Test investigation",

            "findings":
                [
                    {
                        "entity":
                            "John"
                    }
                ],

        }
    )


    assert (
        result["status"]
        ==
        "completed"
    )


    assert (
        result["report"].title
        ==
        "Test Case"
    )


    assert len(
        result["report"].findings
    ) == 1



def test_manager_metadata():

    manager = InvestigationManager()


    metadata = (
        manager.metadata()
    )


    assert (
        metadata["type"]
        ==
        "investigation_manager"
    )


    assert (
        metadata["version"]
        ==
        "1.0"
    )