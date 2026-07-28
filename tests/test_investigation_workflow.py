"""
Tests for InvestigationWorkflow.
"""


from app.application.workflow import (
    InvestigationWorkflow,
)



def test_workflow_execution():

    workflow = InvestigationWorkflow()



    def first_step(data):

        data["step1"] = True

        return data



    def second_step(data):

        data["step2"] = True

        return data



    workflow.add_step(
        first_step
    )


    workflow.add_step(
        second_step
    )



    result = workflow.execute(
        {}
    )


    assert (
        result["step1"]
        is
        True
    )


    assert (
        result["step2"]
        is
        True
    )



def test_workflow_metadata():

    workflow = InvestigationWorkflow()


    metadata = (
        workflow.metadata()
    )


    assert (
        metadata["type"]
        ==
        "investigation_workflow"
    )


    assert (
        metadata["version"]
        ==
        "1.0"
    )