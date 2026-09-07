import inspect

from app.core.service_container import ServiceContainer
from app.application.open_web_enrichment_service import (
    OpenWebEnrichmentService,
    OpenWebEnrichmentResult,
)
from app.application.open_web_recursive_pivot_service import (
    OpenWebRecursivePivotService,
    OpenWebRecursivePivotResult,
)
from app.osint.open_web.contracts import OpenWebQuery

print("=" * 80)
print("M021.15 UI INTEGRATION PROBE")
print("=" * 80)

targets = [
    ServiceContainer,
    OpenWebEnrichmentService,
    OpenWebEnrichmentResult,
    OpenWebRecursivePivotService,
    OpenWebRecursivePivotResult,
    OpenWebQuery,
]

for obj in targets:
    print(f"\n### {obj.__module__}.{obj.__name__}")
    try:
        print("SIGNATURE:", inspect.signature(obj))
    except Exception as exc:
        print("SIGNATURE ERROR:", exc)

    try:
        print(inspect.getsource(obj))
    except Exception as exc:
        print("SOURCE ERROR:", exc)

print("\n" + "=" * 80)
print("CASE WORKSPACE STRUCTURE")
print("=" * 80)

from pathlib import Path

candidates = [
    Path(r"app/interface/desktop/pages/case_workspace_page.py"),
    Path(r"app/interface/desktop/pages/case/workspace_page.py"),
    Path(r"app/interface/desktop/pages/case/_workspace_page.py"),
]

workspace = next(
    (path for path in candidates if path.exists()),
    None,
)

if workspace is None:
    print("CASE_WORKSPACE_FILE: NOT FOUND")
else:
    print("CASE_WORKSPACE_FILE:", workspace)

    text = workspace.read_text(
        encoding="utf-8",
        errors="replace",
    )

    interesting = (
        "class ",
        "def __init__",
        "QTabWidget",
        "addTab(",
        "ServiceContainer",
        "service_container",
        "case_id",
        "_build",
        "_setup",
        "_create",
    )

    for number, line in enumerate(
        text.splitlines(),
        1,
    ):
        if any(token in line for token in interesting):
            print(f"{number:05}: {line}")

print("\n" + "=" * 80)
print("DESKTOP ENTRYPOINTS")
print("=" * 80)

root = Path(r"app/interface/desktop")

for path in sorted(root.rglob("*.py")):
    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if (
        "CaseWorkspace" in text
        or "case_workspace" in text
        or "QStackedWidget" in text
        or "ServiceContainer(" in text
    ):
        print("\nFILE:", path)
        for number, line in enumerate(
            text.splitlines(),
            1,
        ):
            if (
                "CaseWorkspace" in line
                or "case_workspace" in line
                or "QStackedWidget" in line
                or "ServiceContainer(" in line
            ):
                print(f"{number:05}: {line}")
