from __future__ import annotations

import re
import ipaddress
from urllib.parse import urlsplit
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.registry_intelligence.query_detection import detect_registry_query


_USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_.-]{2,64}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9()\-\s]{6,24}$")
_DOMAIN_RE = re.compile(
    r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)


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

            self.status_changed.emit(
                "Запуск специализированных OSINT-источников..."
            )

            osint_result = (
                self.container.osint_enrichment_service.enrich_target(
                    case_id=self.case_id,
                    target_type=target_type,
                    value=normalized,
                    depth=0,
                    timeout=120,
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
                        timeout=30,
                        depth=0,
                    ),
                    case_id=self.case_id,
                )
            )

            recursive_result = None

            if self.recursive:
                if target_type in {
                    OsintTargetType.EMAIL,
                    OsintTargetType.USERNAME,
                }:
                    self.status_changed.emit(
                        "Рекурсивное расширение для email/username "
                        "останется отдельным последующим блоком."
                    )
                else:
                    self.status_changed.emit(
                        "Запуск контролируемого рекурсивного обогащения..."
                    )
                    recursive_result = (
                        self.container.open_web_recursive_pivot_service.expand(
                            case_id=self.case_id,
                            open_web_result=open_web_result,
                            timeout=120,
                        )
                    )

            self.result_ready.emit(
                {
                    "target_type": target_type,
                    "normalized_target": normalized,
                    "open_web": open_web_result,
                    "osint": osint_result,
                    "recursive": recursive_result,
                }
            )
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()
