from __future__ import annotations

import re
import ipaddress
from urllib.parse import urlsplit
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.osint_recursive_enrichment_service import (
    RecursiveEnrichmentProgress,
    RecursiveEnrichmentSeed,
)
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.registry_intelligence.query_detection import detect_registry_query


_USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_.-]{2,64}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9()\-\s]{6,24}$")
_DOMAIN_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


# Interactive desktop limits. These do NOT change backend/free-maximum policy.
# They keep one UI search bounded and observable.
_DESKTOP_CONNECTOR_TIMEOUT = 15
_DESKTOP_RECURSIVE_MAX_TARGETS = 6
_DESKTOP_RECURSIVE_TIME_BUDGET_SECONDS = 150.0
_DESKTOP_RECURSIVE_NEW_ENTITIES_PER_TARGET = 5
_DESKTOP_OPEN_WEB_TIMEOUT = 20
_DESKTOP_OPEN_WEB_RECURSIVE_MAX_TARGETS = 4
_DESKTOP_OPEN_WEB_RECURSIVE_TIME_BUDGET_SECONDS = 90.0
_DESKTOP_OPEN_WEB_RECURSIVE_NEW_ENTITIES_PER_TARGET = 5


def detect_investigation_target(value: str) -> tuple[OsintTargetType, str]:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Введите цель поиска.")

    if raw.startswith(("http://", "https://")):
        parts = urlsplit(raw)
        if not parts.hostname:
            raise ValueError("Некорректный URL.")
        return OsintTargetType.URL, raw

    if _EMAIL_RE.fullmatch(raw):
        return OsintTargetType.EMAIL, raw

    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        pass
    else:
        return OsintTargetType.IP, str(address)

    if _PHONE_RE.fullmatch(raw) or (
        raw.startswith("(")
        and re.fullmatch(r"\([0-9]+\)[0-9()\-\s]+", raw)
    ):
        compact = re.sub(r"[()\-\s]", "", raw)
        return OsintTargetType.PHONE, compact

    if _DOMAIN_RE.fullmatch(raw):
        return OsintTargetType.DOMAIN, raw.lower().rstrip(".")

    if _USERNAME_RE.fullmatch(raw):
        return OsintTargetType.USERNAME, raw.lstrip("@")

    raise ValueError(
        "Не удалось определить тип цели. "
        "Используйте URL, домен, email, телефон или username."
    )


class InvestigationSearchWorker(QObject):
    result_ready = Signal(object)
    failed = Signal(str)
    status_changed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        container,
        case_id: UUID,
        raw_target: str,
        recursive: bool,
    ) -> None:
        super().__init__()
        self.container = container
        self.case_id = case_id
        self.raw_target = raw_target
        self.recursive = recursive

    def _on_recursive_progress(
        self,
        progress: RecursiveEnrichmentProgress,
    ) -> None:
        elapsed = int(progress.elapsed_seconds)

        if progress.phase == "queue_seeded":
            self.status_changed.emit(
                "Recursive OSINT: очередь подготовлена; "
                f"целей в очереди: {progress.queued_targets}."
            )
            return

        if progress.phase == "target_started":
            target_type = (
                progress.target_type.value
                if progress.target_type is not None
                else "target"
            )
            self.status_changed.emit(
                "Recursive OSINT: "
                f"depth={progress.depth} · "
                f"{target_type} · {progress.value} · "
                f"обработано={progress.targets_processed} · "
                f"в очереди={progress.queued_targets} · "
                f"{elapsed}с. Ожидание источников..."
            )
            return

        if progress.phase == "target_finished":
            self.status_changed.emit(
                "Recursive OSINT: цель завершена · "
                f"обработано={progress.targets_processed} · "
                f"findings={progress.persisted_findings} · "
                f"новых Entity={progress.entities_created} · "
                f"{elapsed}с."
            )
            return

        if progress.phase in {"stopped", "completed"}:
            reason = (
                progress.stop_reason.value
                if progress.stop_reason is not None
                else progress.phase
            )
            self.status_changed.emit(
                "Recursive OSINT: "
                f"{reason} · "
                f"обработано={progress.targets_processed} · "
                f"кандидатов={progress.candidates_discovered} · "
                f"{elapsed}с."
            )

    @Slot()
    def run(self) -> None:
        try:
            registry_query = detect_registry_query(self.raw_target)
            if registry_query is not None:
                self.status_changed.emit("Searching public business registries...")
                registry_result = self.container.registry_intelligence_service.enrich(
                    registry_query, case_id=self.case_id,
                )
                self.result_ready.emit({
                    "registry": registry_result, "registry_query": registry_query,
                    "normalized_target": registry_query.value,
                })
                return
            target_type, normalized = detect_investigation_target(
                self.raw_target
            )

            self.status_changed.emit(
                f"Поиск: {target_type.value} — {normalized}"
            )

            # M021.16.4 EMAIL routing
            # M021.16.6.2 USERNAME OSINT routing
            # M021.16.7.7.4 unified specialized + Open-Web flow
            #
            # All target types recognized by Investigation Search first use
            # the already-existing safe/default OSINT enrichment boundary.
            # PivotPolicy + Router remain authoritative for goal/provider
            # selection. The UI does not hard-code individual connectors.

            root_recursive_result = None

            if self.recursive:
                # 05R3 — the desktop checkbox now starts the real production
                # BFS from the ROOT seed. This is the same service proven by
                # the controlled 05R2 live E2E gate.
                self.status_changed.emit(
                    "Запуск специализированного OSINT и автоматических pivot-переходов..."
                )

                root_recursive_result = (
                    self.container.osint_recursive_enrichment_service.enrich(
                        case_id=self.case_id,
                        seeds=(
                            RecursiveEnrichmentSeed(
                                target_type=target_type,
                                value=normalized,
                            ),
                        ),
                        seed_depth=0,
                        timeout=_DESKTOP_CONNECTOR_TIMEOUT,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                        progress_callback=self._on_recursive_progress,
                        max_targets=_DESKTOP_RECURSIVE_MAX_TARGETS,
                        time_budget_seconds=(
                            _DESKTOP_RECURSIVE_TIME_BUDGET_SECONDS
                        ),
                        per_target_new_entity_limit=(
                            _DESKTOP_RECURSIVE_NEW_ENTITIES_PER_TARGET
                        ),
                    )
                )

                if not root_recursive_result.runs:
                    raise RuntimeError(
                        "Рекурсивный OSINT не обработал исходную цель."
                    )

                # The first recursive run is exactly the former one-shot root
                # result, so the existing presentation contract stays intact.
                osint_result = root_recursive_result.runs[0]

            else:
                self.status_changed.emit(
                    "Запуск специализированных OSINT-источников..."
                )

                osint_result = (
                    self.container.osint_enrichment_service.enrich_target(
                        case_id=self.case_id,
                        target_type=target_type,
                        value=normalized,
                        depth=0,
                        timeout=_DESKTOP_CONNECTOR_TIMEOUT,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                    )
                )

            open_web_limit = (
                40
                if target_type is OsintTargetType.EMAIL
                else 25
            )

            self.status_changed.emit(
                "Поиск Open-Web, архивов и публичных документов..."
            )

            open_web_result = (
                self.container.open_web_enrichment_service.enrich(
                    OpenWebQuery(
                        target_type=target_type,
                        value=normalized,
                        case_id=str(self.case_id),
                        limit=open_web_limit,
                        timeout=_DESKTOP_OPEN_WEB_TIMEOUT,
                        depth=0,
                    ),
                    case_id=self.case_id,
                )
            )

            open_web_recursive_result = None

            if self.recursive:
                # Open-Web may discover persisted entities that the specialized
                # root recursion did not see. Feed them into the SAME traversal
                # state so visited guards and entity/pivot budgets remain global.
                self.status_changed.emit(
                    "Добавление Open-Web сущностей в общий рекурсивный поиск..."
                )

                open_web_recursive_result = (
                    self.container.open_web_recursive_pivot_service.expand(
                        case_id=self.case_id,
                        open_web_result=open_web_result,
                        state=root_recursive_result.state,
                        timeout=_DESKTOP_CONNECTOR_TIMEOUT,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                        progress_callback=self._on_recursive_progress,
                        max_targets=(
                            _DESKTOP_OPEN_WEB_RECURSIVE_MAX_TARGETS
                        ),
                        time_budget_seconds=(
                            _DESKTOP_OPEN_WEB_RECURSIVE_TIME_BUDGET_SECONDS
                        ),
                        per_target_new_entity_limit=(
                            _DESKTOP_OPEN_WEB_RECURSIVE_NEW_ENTITIES_PER_TARGET
                        ),
                    )
                )

            self.result_ready.emit(
                {
                    "target_type": target_type,
                    "normalized_target": normalized,
                    "open_web": open_web_result,
                    "osint": osint_result,
                    "recursive": root_recursive_result,
                    "open_web_recursive": open_web_recursive_result,
                }
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()
