"""
Critical import smoke check for the final post-Astra baseline.

No database writes.
No network calls.
No provider connections.
"""

from app.core.ai_factory import (
    resolve_ai_configuration,
)
from app.application.investigation_analysis_runner import (
    InvestigationAnalysisRunner,
)
from app.application.investigation_analysis_orchestrator import (
    InvestigationAnalysisOrchestrator,
)
from app.services.telegram_import_service import (
    TelegramImportService,
)
from app.interface.desktop.desktop_app import (
    DesktopApplication,
)


def main() -> None:
    print(
        "AI configuration:",
        resolve_ai_configuration(),
    )
    print(
        "InvestigationAnalysisRunner:",
        InvestigationAnalysisRunner.__name__,
    )
    print(
        "InvestigationAnalysisOrchestrator:",
        InvestigationAnalysisOrchestrator.__name__,
    )
    print(
        "TelegramImportService:",
        TelegramImportService.__name__,
    )
    print(
        "DesktopApplication:",
        DesktopApplication.__name__,
    )
    print(
        "Critical import smoke check: PASS"
    )


if __name__ == "__main__":
    main()
