"""
Tests for CLIInterface.
"""


from app.interface.cli import (
    CLIInterface,
)



def test_cli_without_handler():

    cli = CLIInterface()


    result = cli.handle(
        "test"
    )


    assert (
        result["status"]
        ==
        "no_handler"
    )



def test_cli_with_handler():

    def handler(
        request
    ):

        return {

            "received":
                request

        }


    cli = CLIInterface(
        handler
    )


    result = cli.handle(
        "hello"
    )


    assert (
        result["received"]
        ==
        "hello"
    )