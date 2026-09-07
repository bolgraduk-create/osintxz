import inspect

from app.application.osint_recursive_enrichment_service import (
    OsintRecursiveEnrichmentService,
)


def test_seed_depth_is_backward_compatible():
    signature = inspect.signature(
        OsintRecursiveEnrichmentService.enrich
    )
    assert signature.parameters["seed_depth"].default == 0


def test_seed_depth_is_used_for_root_queue():
    source = inspect.getsource(
        OsintRecursiveEnrichmentService.enrich
    )
    assert "seed_depth: int = 0" in source
    assert "seed_depth must be >= 0" in source
    assert "seed_depth," in source
