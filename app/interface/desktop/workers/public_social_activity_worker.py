from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from PySide6.QtCore import QObject, Signal, Slot

from app.application.public_social_activity import (
    PublicSocialActivityCollector,
    PublicSocialActivityPersistenceService,
)
from app.models.entity import EntityType


class PublicSocialActivityWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        account: dict[str, Any],
        person_entity_id: str,
        limit: int = 50,
    ) -> None:
        super().__init__()
        self.account = dict(account)
        self.person_entity_id = str(person_entity_id or "").strip()
        self.limit = max(1, min(int(limit), 100))

    @Slot()
    def run(self) -> None:
        from app.core.service_container import ServiceContainer
        from app.database.session import create_session

        started = perf_counter()
        container = None
        session = None
        try:
            session = create_session()
            container = ServiceContainer(session)

            person = container.entity_service.get_entity(UUID(self.person_entity_id))
            if person is None:
                raise ValueError("Selected person no longer exists.")
            entity_type = getattr(person, "entity_type", None)
            entity_value = str(getattr(entity_type, "value", entity_type) or "")
            if entity_value != EntityType.PERSON.value:
                raise ValueError("Public activity can only be attached to a PERSON.")

            collector = PublicSocialActivityCollector()
            result = collector.collect(self.account, limit=self.limit)
            snapshot = result.to_dict()

            if result.status == "success":
                persistence = PublicSocialActivityPersistenceService(
                    source_service=container.source_service,
                    evidence_service=container.evidence_service,
                    evidence_link_service=container.evidence_link_service,
                )
                counts = persistence.persist(
                    person=person,
                    platform=result.platform,
                    username=result.username,
                    items=list(snapshot.get("items") or []),
                )
                container.commit()
                snapshot["persistence"] = counts
            else:
                container.rollback()
                snapshot["persistence"] = {"created": 0, "duplicates": 0}

            self.succeeded.emit({
                "snapshot": snapshot,
                "duration": perf_counter() - started,
            })
        except Exception as exc:
            try:
                if container is not None:
                    container.rollback()
                elif session is not None:
                    session.rollback()
            except Exception:
                pass
            self.failed.emit({
                "error": str(exc),
                "duration": perf_counter() - started,
            })
        finally:
            try:
                if container is not None:
                    container.close()
                elif session is not None:
                    session.close()
            except Exception:
                pass
