import inspect

from app.osint.pivot_candidates import (
    RecursivePivotCandidate,
    OsintPivotCandidatePolicy,
)
from app.application.osint_recursive_enrichment_service import (
    RecursiveEnrichmentSeed,
    RecursiveEnrichmentResult,
    OsintRecursiveEnrichmentService,
)
from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentResult,
)
from app.osint.finding_persistence import (
    OsintPersistenceResult,
)

targets = [
    RecursivePivotCandidate,
    OsintPivotCandidatePolicy,
    RecursiveEnrichmentSeed,
    RecursiveEnrichmentResult,
    OsintRecursiveEnrichmentService,
    OpenWebEnrichmentResult,
    OsintPersistenceResult,
]

print("=" * 72)
print("M021.14 CONTRACT PROBE")
print("=" * 72)

for obj in targets:
    print(f"\n### {obj.__module__}.{obj.__name__}")
    try:
        print("SIGNATURE:", inspect.signature(obj))
    except Exception as exc:
        print("SIGNATURE ERROR:", exc)

    try:
        source = inspect.getsource(obj)
    except Exception as exc:
        print("SOURCE ERROR:", exc)
    else:
        print(source)
