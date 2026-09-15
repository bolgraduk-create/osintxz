"""FastAPI boundary for centrally indexed public registries.

The backend exposes normalized RegistryProviderResult objects, never direct SQL
access and never raw mirror tables. Liveness is process-only; readiness is
provider-aware so one registry can be rebuilding without taking unrelated
providers offline.
"""
from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import inspect as sqlalchemy_inspect, text
from sqlalchemy.orm import Session

from app.registry_backend.database import create_registry_read_session
from app.registry_backend.schemas import RegistryQueryRequest
from app.registry_backend.settings import backend_settings
from app.registry_intelligence.providers.ukraine_edr import UkraineEdrRegistryProvider
from app.registry_intelligence.providers.ukraine_edrsr import UkraineEdrsrRegistryProvider
from app.registry_intelligence.registry import RegistryProviderRegistry
from app.registry_intelligence.transport import registry_provider_result_to_wire
from app.repositories.registry_ua_edr_repository import UaEdrRepository
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


SessionFactory = Callable[[], Session]


def _configured_token() -> str | None:
    return backend_settings.api_token_value()


def _authorize(authorization: str | None, expected_token: str | None) -> None:
    if expected_token is None:
        return
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=401,
            detail="Registry Backend authentication required.",
        )
    supplied = authorization[len(prefix):].strip()
    if not supplied or not secrets.compare_digest(supplied, expected_token):
        raise HTTPException(status_code=401, detail="Invalid Registry Backend credentials.")


def _registry_for_session(session: Session) -> RegistryProviderRegistry:
    registry = RegistryProviderRegistry()
    registry.register(
        UkraineEdrRegistryProvider(
            repository=UaEdrRepository(session),
        )
    )
    registry.register(
        UkraineEdrsrRegistryProvider(
            repository=UaEdrsrRepository(session),
        )
    )
    return registry


def _has_table(session: Session, table_name: str) -> bool:
    bind = session.get_bind()
    try:
        return bool(sqlalchemy_inspect(bind).has_table(table_name))
    except Exception:
        return False


def _edr_readiness(session: Session) -> dict:
    if not _has_table(session, "registry_ua_edr_sync_state"):
        return {
            "ready": False,
            "status": "missing",
            "active_generation": None,
            "company_records": 0,
            "sole_trader_records": 0,
        }

    repository = UaEdrRepository(session)
    state = repository.get_sync_state()
    ready = bool(
        state is not None
        and state.status == "ready"
        and state.active_generation
    )
    return {
        "ready": ready,
        "status": state.status if state is not None else "missing",
        "active_generation": state.active_generation if state is not None else None,
        "company_records": int(state.uo_record_count) if state is not None else 0,
        "sole_trader_records": int(state.fop_record_count) if state is not None else 0,
    }


def _edrsr_readiness(session: Session) -> dict:
    if not _has_table(session, "registry_ua_edrsr_sync_state"):
        return {
            "ready": False,
            "status": "missing",
            "ready_years": [],
            "active_generations": {},
            "decision_records": 0,
        }

    repository = UaEdrsrRepository(session)
    states = repository.ready_states()
    ready_years = [int(state.dataset_year) for state in states]
    active_generations = {
        str(state.dataset_year): state.active_generation
        for state in states
        if state.active_generation
    }
    return {
        "ready": bool(states),
        "status": "ready" if states else "missing",
        "ready_years": ready_years,
        "active_generations": active_generations,
        "decision_records": sum(int(state.record_count or 0) for state in states),
    }


def _readiness(session: Session) -> dict:
    session.execute(text("SELECT 1"))
    providers = {
        "ua_edr_business": _edr_readiness(session),
        "ua_edrsr": _edrsr_readiness(session),
    }
    # Registry Backend is operational if its database is reachable and at least
    # one centrally indexed provider is currently usable. Provider endpoints
    # still enforce their own readiness independently.
    return {
        "ready": any(bool(item.get("ready")) for item in providers.values()),
        "providers": providers,
    }


def create_registry_backend_app(
    *,
    session_factory: SessionFactory | None = None,
    auth_token: str | None = None,
) -> FastAPI:
    make_session = session_factory or create_registry_read_session
    expected_token = auth_token if auth_token is not None else _configured_token()

    application = FastAPI(
        title="OSINTXZ Registry Backend",
        version="0.1.0",
        docs_url="/docs" if backend_settings.debug else None,
        redoc_url=None,
    )

    @application.get("/health/live")
    def health_live() -> dict:
        return {
            "status": "ok",
            "service": "registry_backend",
        }

    @application.get("/health/ready")
    def health_ready():
        session = make_session()
        try:
            try:
                readiness = _readiness(session)
            except Exception:
                session.rollback()
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not_ready",
                        "service": "registry_backend",
                        "providers": {},
                    },
                )
            status_code = 200 if readiness["ready"] else 503
            return JSONResponse(
                status_code=status_code,
                content={
                    "status": "ok" if readiness["ready"] else "not_ready",
                    "service": "registry_backend",
                    "providers": readiness["providers"],
                },
            )
        finally:
            session.close()

    @application.get("/health")
    def health() -> dict:
        session = make_session()
        try:
            try:
                readiness = _readiness(session)
            except Exception:
                session.rollback()
                return {
                    "status": "degraded",
                    "service": "registry_backend",
                    "providers": {},
                }
            return {
                "status": "ok" if readiness["ready"] else "degraded",
                "service": "registry_backend",
                "providers": readiness["providers"],
            }
        finally:
            session.close()

    @application.post("/v1/providers/{provider_name}/search")
    def provider_search(
        provider_name: str,
        request: RegistryQueryRequest,
        authorization: str | None = Header(default=None),
    ) -> dict:
        _authorize(authorization, expected_token)
        normalized_provider = (provider_name or "").strip().casefold()
        session = make_session()
        try:
            registry = _registry_for_session(session)
            provider = registry.get(normalized_provider)
            if provider is None:
                raise HTTPException(status_code=404, detail="Unknown registry provider.")

            try:
                readiness = _readiness(session)
            except Exception as exc:
                session.rollback()
                raise HTTPException(
                    status_code=503,
                    detail="Registry Backend database is not ready.",
                ) from exc

            provider_state = readiness["providers"].get(normalized_provider) or {}
            if not provider_state.get("ready"):
                raise HTTPException(
                    status_code=503,
                    detail="Registry provider is not ready.",
                )

            query = request.to_contract()
            if query.sources and normalized_provider not in query.sources:
                raise HTTPException(
                    status_code=400,
                    detail="Requested source does not match endpoint provider.",
                )
            if not provider.supports(query):
                raise HTTPException(
                    status_code=400,
                    detail="Query is not supported by this registry provider.",
                )

            result = provider.search(query)
            payload = registry_provider_result_to_wire(result)
            payload.setdefault("metadata", {})["served_by"] = "registry_backend"
            return payload
        finally:
            session.close()

    return application


app = create_registry_backend_app()
