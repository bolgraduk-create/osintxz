"""
Apply Stabilization 06 to app/core/service_container.py.

Adds the modern InvestigationAnalysisRunner to the composition root
without replacing the whole ServiceContainer file.

The patch is:
- narrow
- idempotent
- backup-producing
- syntax-checked after modification
"""

from __future__ import annotations

from pathlib import Path
import py_compile
import shutil


ROOT = Path(__file__).resolve().parents[1]

TARGET = (
    ROOT
    / "app"
    / "core"
    / "service_container.py"
)

BACKUP = TARGET.with_name(
    "service_container.py.stabilization06.bak"
)


IMPORT_ANCHOR = """from app.application.investigation_analysis_orchestrator import (
    InvestigationAnalysisOrchestrator,
)
"""

RUNNER_IMPORT = """
from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)
"""


WORKSPACE_ANCHOR = """        # ==================================================
        # Workspace Services
        # ==================================================
"""

RUNNER_WIRING = """        # ==================================================
        # Investigation Analysis Runner
        # ==================================================

        self.investigation_analysis_runner = (
            InvestigationAnalysisRunner(
                orchestrator=(
                    self.investigation_analysis_orchestrator
                ),
            )
        )

"""


def main() -> None:

    if not TARGET.exists():
        raise FileNotFoundError(
            f"ServiceContainer not found: {TARGET}"
        )

    source = TARGET.read_text(
        encoding="utf-8",
    )

    original = source

    if (
        "from app.application.investigation_analysis_runner import"
        not in source
    ):

        if IMPORT_ANCHOR not in source:
            raise RuntimeError(
                "Import anchor was not found. "
                "ServiceContainer layout differs from the reviewed version."
            )

        source = source.replace(
            IMPORT_ANCHOR,
            IMPORT_ANCHOR + RUNNER_IMPORT,
            1,
        )

    if (
        "self.investigation_analysis_runner ="
        not in source
    ):

        if WORKSPACE_ANCHOR not in source:
            raise RuntimeError(
                "Workspace Services anchor was not found. "
                "ServiceContainer layout differs from the reviewed version."
            )

        source = source.replace(
            WORKSPACE_ANCHOR,
            RUNNER_WIRING + WORKSPACE_ANCHOR,
            1,
        )

    if source == original:

        print(
            "Stabilization 06 is already applied."
        )

    else:

        if not BACKUP.exists():

            shutil.copy2(
                TARGET,
                BACKUP,
            )

            print(
                f"Backup created: {BACKUP}"
            )

        TARGET.write_text(
            source,
            encoding="utf-8",
            newline="\n",
        )

        print(
            f"Updated: {TARGET}"
        )

    py_compile.compile(
        str(TARGET),
        doraise=True,
    )

    print(
        "ServiceContainer syntax check: PASS"
    )

    updated = TARGET.read_text(
        encoding="utf-8",
    )

    required = (
        "from app.application.investigation_analysis_runner import",
        "self.investigation_analysis_runner =",
        "self.investigation_analysis_orchestrator",
    )

    missing = [
        item
        for item in required
        if item not in updated
    ]

    if missing:
        raise RuntimeError(
            "Post-patch validation failed. Missing: "
            + ", ".join(
                missing
            )
        )

    print(
        "Stabilization 06 wiring validation: PASS"
    )


if __name__ == "__main__":
    main()
