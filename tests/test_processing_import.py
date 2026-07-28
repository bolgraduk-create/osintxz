"""
Processing layer import test.
"""


def test_processing_imports():

    from app.processing import (
        BaseProcessor,
        FileProcessor,
        DocumentProcessor,
        MessageProcessor,
    )


    assert BaseProcessor
    assert FileProcessor
    assert DocumentProcessor
    assert MessageProcessor